import os

class FileManager:
    def __init__(self, filename, piece_length):
        self.filename = filename
        self.piece_length = piece_length
        self.file = open(self.filename, 'r+b') # Open existing file for read/write

    def write_block(self, piece_index, block_offset, data):
        # 1. Calculate the exact position in the file
        global_offset = (piece_index * self.piece_length) + block_offset

        # 2. Move the file pointer to that position
        self.file.seek(global_offset)

        # 3. Write the data
        self.file.write(data)

        # 4. (Optional) Force save to disk immediately so we don't lose data on crash
        self.file.flush()

        print(f"[Disk] Wrote {len(data)} bytes to position {global_offset}")

    def close(self):
        self.file.close()


# Helper to create an empty dummy file before we start
def create_empty_file(filename, total_size):
    if not os.path.exists(filename):
        print(f"Creating empty file: {filename} ({total_size} bytes)")
        with open(filename, 'wb') as f:
            f.seek(total_size - 1)
            f.write(b'\0')