import argparse
import json
import os
import shutil
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk
from PIL import Image, ImageTk
from pillow_heif import register_heif_opener, register_avif_opener

register_heif_opener()
register_avif_opener()


class ImageComparerApp:
    def __init__(self, master: ctk.CTk, json_file: str, output_json: str, moved_images_dir: str) -> None:
        self.master: ctk.CTk = master
        self.master.title("Image Comparer")
        self.master.geometry("1400x800")
        self.output_json = Path(output_json)  # Store output JSON path
        self.to_move_path = Path(moved_images_dir)  # Store moved images directory path
        self.to_move_path.mkdir(exist_ok=True)  # Create moved images directory if it doesn't exist

        with open(json_file, 'rt', encoding='utf-8') as f:
            similar_images = json.load(f)

        # Keep track of filtered and skipped items
        filtered_images = []

        for item in similar_images:
            img1_exists = os.path.exists(item['img1'])
            img2_exists = os.path.exists(item['img2'])

            if img1_exists and img2_exists:
                filtered_images.append(item)
            else:
                print("Skipped pair:")
                print(f"  img1: {item['img1']} - {'Exists' if img1_exists else 'Missing'}")
                print(f"  img2: {item['img2']} - {'Exists' if img2_exists else 'Missing'}")

        self.similar_images = filtered_images
        self.current_index: int = 0
        self.total_pairs: int = len(self.similar_images)

        # Frames to hold images with fixed size
        self.left_frame = ctk.CTkFrame(master, width=600, height=600)
        self.left_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        self.right_frame = ctk.CTkFrame(master, width=600, height=600)
        self.right_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")

        # Image labels inside frames
        self.left_image_label = ctk.CTkLabel(self.left_frame, text="")
        self.left_image_label.place(relx=0.5, rely=0.5, anchor="center")
        self.right_image_label = ctk.CTkLabel(self.right_frame, text="")
        self.right_image_label.place(relx=0.5, rely=0.5, anchor="center")

        # Separate labels for path and size
        # Left side
        self.left_path_label = ctk.CTkLabel(master, text="", justify="right", wraplength=600)
        self.left_path_label.grid(row=1, column=0, padx=10, pady=(10, 0), sticky="nsew")
        self.left_size_label = ctk.CTkLabel(master, text="", justify="right", wraplength=600)
        self.left_size_label.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="nsew")

        # Right side
        self.right_path_label = ctk.CTkLabel(master, text="", justify="left", wraplength=600)
        self.right_path_label.grid(row=1, column=1, padx=10, pady=(10, 0), sticky="nsew")
        self.right_size_label = ctk.CTkLabel(master, text="", justify="left", wraplength=600)
        self.right_size_label.grid(row=2, column=1, padx=10, pady=(0, 10), sticky="nsew")

        # Distance score label with counter
        self.score_label = ctk.CTkLabel(master, text="", justify="center")
        self.score_label.grid(row=3, column=0, columnspan=2, padx=10, pady=10, sticky="ew")

        # Buttons
        self.delete_left_button = ctk.CTkButton(master, text="Delete Left Image", command=self.delete_left_image)
        self.delete_left_button.grid(row=4, column=0, padx=10, pady=10, sticky="ew")
        self.delete_right_button = ctk.CTkButton(master, text="Delete Right Image", command=self.delete_right_image)
        self.delete_right_button.grid(row=4, column=1, padx=10, pady=10, sticky="ew")
        self.next_button = ctk.CTkButton(master, text="Next Pair", command=self.next_pair)
        self.next_button.grid(row=5, column=0, columnspan=2, pady=20, sticky="ew")

        # Configure grid weights for consistent layout
        self.master.grid_rowconfigure(0, weight=1)  # Image row expands
        self.master.grid_rowconfigure(1, weight=0)  # Path row fixed
        self.master.grid_rowconfigure(2, weight=0)  # Size row fixed
        self.master.grid_rowconfigure(3, weight=0)  # Score row fixed
        self.master.grid_rowconfigure(4, weight=0)  # Delete buttons row fixed
        self.master.grid_rowconfigure(5, weight=0)  # Next button row fixed
        self.master.grid_columnconfigure(0, weight=1)
        self.master.grid_columnconfigure(1, weight=1)

        self.left_image: ImageTk.PhotoImage
        self.right_image: ImageTk.PhotoImage

        self.display_current_pair()

    def display_current_pair(self) -> None:
        if self.current_index >= self.total_pairs:
            messagebox.showinfo("End", "No more image pairs to display.")
            return

        pair = self.similar_images[self.current_index]
        img1_path = Path(pair['img1'])
        img2_path = Path(pair['img2'])
        distance = pair['distance']
        img1_codec = pair['img1_codec']
        img2_codec = pair['img2_codec']
        img1_size: tuple[int, int] = pair['img1_size']
        img2_size: tuple[int, int] = pair['img2_size']

        try:
            img1 = Image.open(img1_path)
        except (FileNotFoundError, OSError) as e:
            print(f"Warning: Could not load {img1_path}: {e}")
            self.next_pair()
            return

        try:
            img2 = Image.open(img2_path)
        except (FileNotFoundError, OSError) as e:
            print(f"Warning: Could not load {img2_path}: {e}")
            self.next_pair()
            return

        # Get file sizes
        img1_file_size = os.path.getsize(img1_path)
        img2_file_size = os.path.getsize(img2_path)

        # Calculate resolution (width × height)
        img1_resolution = img1_size[0] * img1_size[1]
        img2_resolution = img2_size[0] * img2_size[1]

        # Codec priority (AVIF > HEIF > PNG > Others)
        codec_priority = {'avif': 3, 'heif': 2, 'png': 1}
        img1_codec_score = codec_priority.get(img1_codec.lower(), 0)
        img2_codec_score = codec_priority.get(img2_codec.lower(), 0)

        # Determine if img2 should be on the left (swap) and which is better
        swap = False
        better_resolution = False
        better_codec = False
        img1_is_better = False

        if img1_resolution < img2_resolution:
            swap = better_resolution = True
        elif img1_resolution > img2_resolution:
            img1_is_better = True
            better_resolution = True
        elif img1_resolution == img2_resolution:
            if img1_codec_score < img2_codec_score:
                swap = better_codec = True
            elif img1_codec_score > img2_codec_score:
                img1_is_better = True
                better_codec = True
            elif img1_file_size < img2_file_size:
                swap = True
            elif img1_file_size > img2_file_size:
                img1_is_better = True

        # Assign images and info based on swap
        if swap:
            left_img = img2
            right_img = img1
            left_path = img2_path
            right_path = img1_path
            left_size = img2_size
            right_size = img1_size
        else:
            left_img = img1
            right_img = img2
            left_path = img1_path
            right_path = img2_path
            left_size = img1_size
            right_size = img2_size

        left_img.thumbnail((600, 600))
        right_img.thumbnail((600, 600))

        self.left_image = ImageTk.PhotoImage(left_img)
        self.right_image = ImageTk.PhotoImage(right_img)

        self.left_image_label.configure(image=self.left_image)
        self.right_image_label.configure(image=self.right_image)

        # Determine colors based on which image is better
        left_path_color = "#FFFFFF"
        left_size_color = "#FFFFFF"
        right_path_color = "#FFFFFF"
        right_size_color = "#FFFFFF"

        if swap:  # img2 is better (on the left)
            if better_resolution:
                left_size_color = "#00FF00"  # Green for resolution
            elif better_codec:
                left_path_color = "#00FF00"  # Green for codec
        else:  # img1 is better (on the left) or no difference
            if img1_is_better:
                if better_resolution:
                    left_size_color = "#00FF00"  # Green for resolution
                elif better_codec:
                    left_path_color = "#00FF00"  # Green for codec

        # Set text and colors
        self.left_path_label.configure(text=f"{left_path}", text_color=left_path_color)
        self.left_size_label.configure(text=f"Size: {left_size[0]}x{left_size[1]}", text_color=left_size_color)
        self.right_path_label.configure(text=f"{right_path}", text_color=right_path_color)
        self.right_size_label.configure(text=f"Size: {right_size[0]}x{right_size[1]}", text_color=right_size_color)

        # Distance color: red if > 0, white otherwise
        score_color = "#FF0000" if distance > 0 else "#FFFFFF"
        score_text = f"Distance Score: {distance}\nPair {self.current_index + 1}/{self.total_pairs}"
        self.score_label.configure(text=score_text, text_color=score_color)

    def delete_left_image(self) -> None:
        if self.current_index < len(self.similar_images):
            self.delete_image('img1')

    def delete_right_image(self) -> None:
        if self.current_index < len(self.similar_images):
            self.delete_image('img2')

    def delete_image(self, img_str: str):
        if self.current_index >= len(self.similar_images):
            return

        img_path = Path(self.similar_images[self.current_index][img_str])
        try:
            dest_path = self.to_move_path / img_path.name
            shutil.move(img_path, dest_path)
            print(f"Moved {img_path} to {dest_path}")
            # Remove the current pair from the list
        except Exception as e:
            messagebox.showerror("Error", f"Could not move {img_path}: {e}")
        self.next_pair()

    def next_pair(self) -> None:
        self.current_index += 1
        self.display_current_pair()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Image Comparer: A GUI tool to compare and manage similar image pairs based on a JSON input file."
    )
    parser.add_argument(
        "-ij", "--input_json",
        type=str,
        required=True,
        help="Path to the input JSON file containing pairs of similar images with their paths and distance scores."
    )
    parser.add_argument(
        "-oj", "--output_json",
        type=str,
        required=True,
        help="Path where the filtered JSON file with remaining unprocessed image pairs will be saved."
    )
    parser.add_argument(
        "-mid", "--moved_images_dir",
        type=str,
        default="moved_images",
        help="Directory where deleted (moved) images will be stored. Default is 'moved_images'."
    )
    args = parser.parse_args()

    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    root: ctk.CTk = ctk.CTk()
    app: ImageComparerApp = ImageComparerApp(root, args.input_json, args.output_json, args.moved_images_dir)
    root.mainloop()
