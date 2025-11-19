# file_encrypter.py

import os
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
import base64
import struct

from cryptography.fernet import Fernet
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding, hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.asymmetric import rsa, padding as rsa_padding
from cryptography.hazmat.primitives import serialization

# --- Encryption Algorithm Implementations ---

class FernetCipher:
    """
    A class to handle encryption and decryption using the Fernet algorithm,
    which is built on AES. This is the recommended symmetric choice.
    """
    def __init__(self, key):
        """Initializes the Fernet cipher with a given key."""
        self.cipher = Fernet(key)

    def encrypt(self, data):
        """Encrypts data using Fernet."""
        return self.cipher.encrypt(data)

    def decrypt(self, data):
        """Decrypts data using Fernet."""
        return self.cipher.decrypt(data)

class DESCipher:
    """
    A class to handle encryption and decryption using the DES algorithm.
    WARNING: DES is an outdated and insecure algorithm. Use Fernet instead.
    """
    def __init__(self, key, iv):
        """Initializes the DES cipher with a given key and IV."""
        self.key = key
        self.iv = iv
        self.backend = default_backend()
        self.algorithm = algorithms.TripleDES(self.key)
        self.mode = modes.CBC(self.iv)

    def encrypt(self, data):
        """Encrypts data using DES."""
        padder = padding.PKCS7(self.algorithm.block_size).padder()
        padded_data = padder.update(data) + padder.finalize()
        cipher = Cipher(self.algorithm, self.mode, backend=self.backend)
        encryptor = cipher.encryptor()
        return encryptor.update(padded_data) + encryptor.finalize()

    def decrypt(self, data):
        """Decrypts data using DES."""
        cipher = Cipher(self.algorithm, self.mode, backend=self.backend)
        decryptor = cipher.decryptor()
        decrypted_padded_data = decryptor.update(data) + decryptor.finalize()
        unpadder = padding.PKCS7(self.algorithm.block_size).unpadder()
        return unpadder.update(decrypted_padded_data) + unpadder.finalize()

class RSACipher:
    """
    A class to handle hybrid encryption using RSA.
    The file is encrypted with a temporary Fernet key, which is then
    encrypted using the RSA public key.
    """
    def __init__(self, key):
        self.key = key

    def encrypt(self, data):
        """
        Encrypts data using a temporary Fernet key, which is then encrypted
        with the RSA public key. Returns the encrypted Fernet key and data.
        """
        # Generate a temporary symmetric key (Fernet)
        fernet_key = Fernet.generate_key()
        fernet_cipher = FernetCipher(fernet_key)
        encrypted_data = fernet_cipher.encrypt(data)
        
        # Encrypt the symmetric key with the RSA public key
        encrypted_fernet_key = self.key.encrypt(
            fernet_key,
            rsa_padding.OAEP(
                mgf=rsa_padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        return encrypted_fernet_key, encrypted_data
        
    def decrypt(self, encrypted_fernet_key, encrypted_data):
        """
        Decrypts the Fernet key with the RSA private key and then
        decrypts the file data.
        """
        # Decrypt the symmetric key with the RSA private key
        fernet_key = self.key.decrypt(
            encrypted_fernet_key,
            rsa_padding.OAEP(
                mgf=rsa_padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        fernet_cipher = FernetCipher(fernet_key)
        return fernet_cipher.decrypt(encrypted_data)

# --- Main Application UI ---

class FileCrypterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("File Encryption and Decryption Tool")
        self.geometry("600x600")
        self.resizable(False, False)

        # File Paths and Keys
        self.input_file = None
        self.symmetric_key = None
        self.rsa_public_key = None
        self.rsa_private_key = None

        # UI elements
        self.create_widgets()
        self.update_key_widgets()

    def create_widgets(self):
        """Creates and packs all the widgets for the UI."""
        main_frame = ttk.Frame(self, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Encryption Algorithm Selection
        ttk.Label(main_frame, text="Select Algorithm:", font=("Helvetica", 12, "bold")).pack(pady=(10, 5))
        self.algorithm_var = tk.StringVar(value="Fernet (AES) - Recommended")
        
        alg_frame = ttk.Frame(main_frame)
        alg_frame.pack(pady=5)
        ttk.Radiobutton(alg_frame, text="Fernet (AES) - Recommended", variable=self.algorithm_var, value="Fernet (AES) - Recommended", command=self.update_key_widgets).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(alg_frame, text="DES", variable=self.algorithm_var, value="DES", command=self.update_key_widgets).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(alg_frame, text="RSA (Public/Private Key)", variable=self.algorithm_var, value="RSA", command=self.update_key_widgets).pack(side=tk.LEFT, padx=5)

        # File Selection Frame
        file_frame = ttk.LabelFrame(main_frame, text="File Selection", padding="10")
        file_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(file_frame, text="Select File to Process", command=self.select_file).pack(fill=tk.X, pady=5)
        self.file_label = ttk.Label(file_frame, text="No file selected.")
        self.file_label.pack(pady=5)

        # Key Management Frame
        self.key_management_frame = ttk.LabelFrame(main_frame, text="Key Management", padding="10")
        self.key_management_frame.pack(fill=tk.X, pady=10)

        # Action Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Encrypt File", command=self.encrypt_file).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        ttk.Button(button_frame, text="Decrypt File", command=self.decrypt_file).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        
        # Progress Bar and Status
        self.progress_label = ttk.Label(main_frame, text="Ready.", anchor=tk.W)
        self.progress_label.pack(fill=tk.X, pady=(5, 0))
        self.progressbar = ttk.Progressbar(main_frame, orient="horizontal", length=400, mode="determinate")
        self.progressbar.pack(fill=tk.X, pady=(0, 10))

        # Status Bar
        self.status_label = ttk.Label(main_frame, text="", relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X)

    def update_key_widgets(self):
        """Dynamically updates the key management frame based on the selected algorithm."""
        for widget in self.key_management_frame.winfo_children():
            widget.destroy()

        alg = self.algorithm_var.get()

        if alg in ["Fernet (AES) - Recommended", "DES"]:
            # Symmetric Key UI
            ttk.Label(self.key_management_frame, text="Symmetric Key:").pack(pady=(0, 5))
            key_button_frame = ttk.Frame(self.key_management_frame)
            key_button_frame.pack(fill=tk.X)
            ttk.Button(key_button_frame, text="Generate New Key", command=self.generate_symmetric_key).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
            ttk.Button(key_button_frame, text="Load Key from File", command=self.load_symmetric_key).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
            self.save_key_button = ttk.Button(key_button_frame, text="Save Key", command=self.save_symmetric_key, state="disabled")
            self.save_key_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
            self.key_entry = ttk.Entry(self.key_management_frame, state="readonly", width=50)
            self.key_entry.pack(pady=5, fill=tk.X)
        else: # RSA
            # Asymmetric Key UI
            ttk.Label(self.key_management_frame, text="RSA Key Pair:").pack(pady=(0, 5))
            key_gen_button = ttk.Button(self.key_management_frame, text="Generate New Key Pair", command=self.generate_rsa_key_pair)
            key_gen_button.pack(fill=tk.X, pady=5)
            
            pub_key_frame = ttk.Frame(self.key_management_frame)
            pub_key_frame.pack(fill=tk.X)
            ttk.Button(pub_key_frame, text="Load Public Key", command=self.load_rsa_public_key).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
            self.pub_key_label = ttk.Label(pub_key_frame, text="No public key loaded.")
            self.pub_key_label.pack(side=tk.LEFT, padx=5)

            priv_key_frame = ttk.Frame(self.key_management_frame)
            priv_key_frame.pack(fill=tk.X)
            ttk.Button(priv_key_frame, text="Load Private Key", command=self.load_rsa_private_key).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
            self.priv_key_label = ttk.Label(priv_key_frame, text="No private key loaded.")
            self.priv_key_label.pack(side=tk.LEFT, padx=5)

    def select_file(self):
        """Opens a file dialog for the user to select a file."""
        self.input_file = filedialog.askopenfilename(
            title="Select File to Process",
            filetypes=[("All Files", "*.*")]
        )
        if self.input_file:
            self.file_label.config(text=f"Selected: {os.path.basename(self.input_file)}")
            self.status_label.config(text="File selected. Ready to encrypt or decrypt.")

    def generate_symmetric_key(self):
        """Generates a new symmetric key."""
        alg = self.algorithm_var.get()
        if "Fernet" in alg:
            self.symmetric_key = Fernet.generate_key()
            self.key_entry.config(state="normal")
            self.key_entry.delete(0, tk.END)
            self.key_entry.insert(0, self.symmetric_key.decode())
            self.key_entry.config(state="readonly")
        else: # DES
            key = os.urandom(24) # 24 bytes for TripleDES
            iv = os.urandom(8)   # 8 bytes for IV
            self.symmetric_key = (key, iv)
            self.key_entry.config(state="normal")
            self.key_entry.delete(0, tk.END)
            self.key_entry.insert(0, base64.urlsafe_b64encode(key + iv).decode())
            self.key_entry.config(state="readonly")
        
        self.save_key_button.config(state="normal")
        self.status_label.config(text=f"{alg} key generated. Remember to save it!")

    def load_symmetric_key(self):
        """Loads a symmetric key from a file."""
        key_file_path = filedialog.askopenfilename(
            title="Load Key from File",
            filetypes=[("Key Files", "*.key"), ("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if not key_file_path:
            return

        try:
            with open(key_file_path, "rb") as f:
                loaded_key_data = f.read().strip()
            
            alg = self.algorithm_var.get()
            if "Fernet" in alg:
                self.symmetric_key = loaded_key_data
                self.key_entry.config(state="normal")
                self.key_entry.delete(0, tk.END)
                self.key_entry.insert(0, self.symmetric_key.decode())
                self.key_entry.config(state="readonly")
            else: # DES
                decoded_key_iv = base64.urlsafe_b64decode(loaded_key_data)
                self.symmetric_key = (decoded_key_iv[:24], decoded_key_iv[24:])
                self.key_entry.config(state="normal")
                self.key_entry.delete(0, tk.END)
                self.key_entry.insert(0, loaded_key_data.decode())
                self.key_entry.config(state="readonly")
            
            self.save_key_button.config(state="normal")
            self.status_label.config(text=f"Key loaded from {os.path.basename(key_file_path)}.")
        except Exception as e:
            messagebox.showerror("Error", f"Could not load key: {e}")

    def save_symmetric_key(self):
        """Saves the current symmetric key to a file."""
        if self.symmetric_key is None:
            messagebox.showwarning("Warning", "No key to save. Please generate or load one first.")
            return

        alg = self.algorithm_var.get()
        if "Fernet" in alg:
            key_data = self.symmetric_key
        else: # DES
            key_data = base64.urlsafe_b64encode(self.symmetric_key[0] + self.symmetric_key[1])

        save_path = filedialog.asksaveasfilename(
            title="Save Key to File",
            defaultextension=".key",
            filetypes=[("Key Files", "*.key"), ("All Files", "*.*")]
        )
        if save_path:
            try:
                with open(save_path, "wb") as f:
                    f.write(key_data)
                self.status_label.config(text=f"Key saved to {os.path.basename(save_path)}.")
                messagebox.showinfo("Success", "Key saved successfully!")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save key: {e}")

    def generate_rsa_key_pair(self):
        """Generates a new RSA public/private key pair."""
        try:
            self.rsa_private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
                backend=default_backend()
            )
            self.rsa_public_key = self.rsa_private_key.public_key()
            self.pub_key_label.config(text="Public key generated.")
            self.priv_key_label.config(text="Private key generated.")
            self.status_label.config(text="RSA key pair generated. Save them to files!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate keys: {e}")
            return
        
        # Save the private key
        save_path = filedialog.asksaveasfilename(
            title="Save Private Key",
            defaultextension=".pem",
            filetypes=[("PEM Files", "*.pem")]
        )
        if save_path:
            with open(save_path, "wb") as f:
                f.write(self.rsa_private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                ))
            messagebox.showinfo("Success", f"Private key saved to {os.path.basename(save_path)}")
        
        # Save the public key
        save_path = filedialog.asksaveasfilename(
            title="Save Public Key",
            defaultextension=".pub",
            filetypes=[("PUB Files", "*.pub")]
        )
        if save_path:
            with open(save_path, "wb") as f:
                f.write(self.rsa_public_key.public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo
                ))
            messagebox.showinfo("Success", f"Public key saved to {os.path.basename(save_path)}")

    def load_rsa_public_key(self):
        """Loads a public key from a file."""
        key_file_path = filedialog.askopenfilename(
            title="Load Public Key",
            filetypes=[("PUB Files", "*.pub"), ("PEM Files", "*.pem")]
        )
        if not key_file_path:
            return
        
        try:
            with open(key_file_path, "rb") as f:
                self.rsa_public_key = serialization.load_pem_public_key(f.read(), backend=default_backend())
            self.pub_key_label.config(text=f"Public key loaded from {os.path.basename(key_file_path)}")
            self.status_label.config(text="Public key loaded. Ready to encrypt.")
        except Exception as e:
            messagebox.showerror("Error", f"Could not load public key: {e}")

    def load_rsa_private_key(self):
        """Loads a private key from a file."""
        key_file_path = filedialog.askopenfilename(
            title="Load Private Key",
            filetypes=[("PEM Files", "*.pem")]
        )
        if not key_file_path:
            return
        
        try:
            with open(key_file_path, "rb") as f:
                self.rsa_private_key = serialization.load_pem_private_key(f.read(), password=None, backend=default_backend())
            self.priv_key_label.config(text=f"Private key loaded from {os.path.basename(key_file_path)}")
            self.status_label.config(text="Private key loaded. Ready to decrypt.")
        except Exception as e:
            messagebox.showerror("Error", f"Could not load private key: {e}")

    def show_data_preview(self, original_data, transformed_data, is_encrypting):
        """
        Creates a new window to show the before and after of data transformation.
        This is for educational purposes with .txt files only.
        """
        preview_window = tk.Toplevel(self)
        preview_window.title("Data Transformation Preview")
        preview_window.geometry("800x600")

        frame = ttk.Frame(preview_window, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        # Before section
        before_frame = ttk.LabelFrame(frame, text="Original Data", padding=10)
        before_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        before_text = tk.Text(before_frame, wrap=tk.WORD, font=("Consolas", 10), state="normal")
        before_text.insert(tk.END, original_data)
        before_text.config(state="disabled")
        before_text.pack(fill=tk.BOTH, expand=True)

        # After section
        after_frame = ttk.LabelFrame(frame, text="Transformed Data", padding=10)
        after_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5)
        after_text = tk.Text(after_frame, wrap=tk.WORD, font=("Consolas", 10), state="normal")
        after_text.insert(tk.END, transformed_data)
        after_text.config(state="disabled")
        after_text.pack(fill=tk.BOTH, expand=True)

        status_label = "This is a demonstration of what encryption does to human-readable data."
        if not is_encrypting:
            status_label = "This is a demonstration of how encrypted data is returned to a human-readable format."
        ttk.Label(frame, text=status_label, anchor=tk.CENTER).pack(side=tk.BOTTOM, pady=5)


    def encrypt_file(self):
        """Encrypts the selected file and saves it."""
        if not self.input_file:
            messagebox.showwarning("Warning", "Please select a file.")
            return

        alg = self.algorithm_var.get()
        if alg == "RSA":
            if not self.rsa_public_key:
                messagebox.showwarning("Warning", "Please load a public key for encryption.")
                return
        elif not self.symmetric_key:
            messagebox.showwarning("Warning", "Please generate/load a key.")
            return

        self.progress_label.config(text="Encrypting...")
        self.progressbar["value"] = 0
        self.update_idletasks()
        
        try:
            with open(self.input_file, "rb") as f:
                data = f.read()

            # Get the original file extension and prepare it for embedding
            original_ext = os.path.splitext(self.input_file)[1]
            ext_bytes = original_ext.encode('utf-8')
            ext_header = struct.pack('!I', len(ext_bytes))

            if alg == "Fernet (AES) - Recommended":
                cipher = FernetCipher(self.symmetric_key)
                encrypted_data = cipher.encrypt(data)
                final_data = ext_header + ext_bytes + encrypted_data
            elif alg == "DES":
                cipher = DESCipher(self.symmetric_key[0], self.symmetric_key[1])
                encrypted_data = cipher.encrypt(data)
                final_data = ext_header + ext_bytes + encrypted_data
            else: # RSA
                cipher = RSACipher(self.rsa_public_key)
                encrypted_key, encrypted_file_data = cipher.encrypt(data)
                # Combine the extension, encrypted key, and encrypted file data
                final_data = ext_header + ext_bytes + encrypted_key + encrypted_file_data

            save_path = filedialog.asksaveasfilename(
                title="Save Encrypted File",
                defaultextension=".encrypted",
                filetypes=[("Encrypted Files", "*.encrypted"), ("All Files", "*.*")]
            )
            if save_path:
                with open(save_path, "wb") as f:
                    f.write(final_data)

                # Show visualization for .txt files
                try:
                    original_text = data.decode('utf-8')
                    transformed_text = base64.b64encode(final_data).decode('utf-8')
                    self.show_data_preview(original_text, transformed_text, is_encrypting=True)
                except UnicodeDecodeError:
                    messagebox.showinfo("Visualization Note", "The selected file is not a text file, so a data preview will not be shown.")
                
                self.progressbar["value"] = 100
                self.progress_label.config(text="Encryption Complete.")
                self.status_label.config(text=f"Successfully encrypted and saved to {os.path.basename(save_path)}")
                messagebox.showinfo("Success", "File encrypted successfully!")
        except Exception as e:
            self.progressbar["value"] = 0
            self.progress_label.config(text="Encryption Failed.")
            messagebox.showerror("Encryption Error", f"An error occurred during encryption: {e}")

    def decrypt_file(self):
        """Decrypts the selected file and saves it."""
        if not self.input_file:
            messagebox.showwarning("Warning", "Please select a file.")
            return

        alg = self.algorithm_var.get()
        if alg == "RSA":
            if not self.rsa_private_key:
                messagebox.showwarning("Warning", "Please load the private key for decryption.")
                return
        elif not self.symmetric_key:
            messagebox.showwarning("Warning", "Please generate/load the key used for encryption.")
            return
        
        self.progress_label.config(text="Decrypting...")
        self.progressbar["value"] = 0
        self.update_idletasks()

        try:
            with open(self.input_file, "rb") as f:
                encrypted_data = f.read()
            
            # Extract the original file extension from the header
            ext_len = struct.unpack('!I', encrypted_data[:4])[0]
            original_ext = encrypted_data[4:4+ext_len].decode('utf-8')
            # The rest of the data is the encrypted content
            encrypted_content = encrypted_data[4+ext_len:]

            if alg == "Fernet (AES) - Recommended":
                cipher = FernetCipher(self.symmetric_key)
                decrypted_data = cipher.decrypt(encrypted_content)
            elif alg == "DES":
                cipher = DESCipher(self.symmetric_key[0], self.symmetric_key[1])
                decrypted_data = cipher.decrypt(encrypted_content)
            else: # RSA
                # Determine the size of the encrypted key based on the RSA key size
                encrypted_key_size = self.rsa_private_key.key_size // 8
                encrypted_key = encrypted_content[:encrypted_key_size]
                encrypted_file_data = encrypted_content[encrypted_key_size:]
                
                cipher = RSACipher(self.rsa_private_key)
                decrypted_data = cipher.decrypt(encrypted_key, encrypted_file_data)
            
            # Show visualization for .txt files
            try:
                original_text = base64.b64encode(encrypted_data).decode('utf-8')
                transformed_text = decrypted_data.decode('utf-8')
                self.show_data_preview(original_text, transformed_text, is_encrypting=False)
            except UnicodeDecodeError:
                messagebox.showinfo("Visualization Note", "The selected file is not a text file, so a data preview will not be shown.")
                
            original_file_name = os.path.basename(os.path.splitext(self.input_file)[0])
            save_path = filedialog.asksaveasfilename(
                title="Save Decrypted File",
                defaultextension=original_ext,
                initialfile=f"{original_file_name}_decrypted",
                filetypes=[(f"Original File (*{original_ext})", f"*{original_ext}"), ("All Files", "*.*")]
            )
            if save_path:
                with open(save_path, "wb") as f:
                    f.write(decrypted_data)
                self.progressbar["value"] = 100
                self.progress_label.config(text="Decryption Complete.")
                self.status_label.config(text=f"Successfully decrypted and saved to {os.path.basename(save_path)}")
                messagebox.showinfo("Success", "File decrypted successfully!")
        except Exception as e:
            self.progressbar["value"] = 0
            self.progress_label.config(text="Decryption Failed.")
            messagebox.showerror("Decryption Error", f"An error occurred during decryption: {e}\n\n"
                                                      "Make sure you have selected the correct key and algorithm.")


if __name__ == "__main__":
    app = FileCrypterApp()
    app.mainloop()
