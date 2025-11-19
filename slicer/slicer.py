import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image
import cv2
import numpy as np
import os

def slice_icons_from_transparent_image(image_path, output_dir="sliced_icons"):
    """
    Slices icons from a PNG image with a transparent background.
    """
    if not image_path:
        messagebox.showwarning("No File Selected", "Please select an image file to process.")
        return

    try:
        pil_img = Image.open(image_path).convert("RGBA")
        np_img = np.array(pil_img)
        alpha_channel = np_img[:, :, 3]
        _, binary_mask = cv2.threshold(alpha_channel, 0, 255, cv2.THRESH_BINARY)
    except FileNotFoundError:
        messagebox.showerror("File Not Found", f"Error: The file '{image_path}' was not found.")
        return
    except Exception as e:
        messagebox.showerror("Processing Error", f"An error occurred: {e}")
        return

    contours, _ = cv2.findContours(binary_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    icon_count = 0
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if w > 5 and h > 5:
            cropped_icon = pil_img.crop((x, y, x + w, y + h))
            output_file_path = os.path.join(output_dir, f"icon_{icon_count}.png")
            cropped_icon.save(output_file_path)
            icon_count += 1

    messagebox.showinfo("Success", f"Successfully sliced and saved {icon_count} icons to '{output_dir}'.")

def select_and_slice():
    """
    Opens a file dialog for the user to select an image and then runs the slicing process.
    """
    # Open a file dialog to select a PNG file
    file_path = filedialog.askopenfilename(
        title="Select Image File",
        filetypes=[("PNG files", "*.png")]
    )
    # Pass the selected file path to the slicing function
    if file_path:
        slice_icons_from_transparent_image(file_path)

# --- GUI Setup ---
if __name__ == "__main__":
    root = tk.Tk()
    root.title("Icon Slicer")
    root.geometry("300x150")

    # Create and place the button
    label = tk.Label(root, text="Click the button to select and slice an image.")
    label.pack(pady=10)

    button = tk.Button(root, text="Select Image", command=select_and_slice)
    button.pack(pady=10)

    # Start the GUI event loop
    root.mainloop()