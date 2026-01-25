import socket
import struct
import time
from file_manager import FileManager, create_empty_file

class PeerConnection:
    BLOCK_SIZE = 16384 # 16KB standard request size

    def __init__(self, ip, port, info_hash, peer_id, file_manager, total_pieces, piece_length):
        self.ip = ip
        self.port = port
        self.info_hash = info_hash # Expecting bytes, not hex string
        self.peer_id = peer_id     # Expecting bytes
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(5)    # Don't hang forever
        self.buffer = b""          # Our stream buffer
        self.available_pieces = set() # We use a Set for fast lookups

        self.file_manager = file_manager

        self.total_pieces = total_pieces
        self.piece_length = piece_length
        self.current_piece = 0
        self.current_offset = 0

        self.am_choked = True


    def connect(self):
        try:
            print(f"Connecting to {self.ip}:{self.port}...")
            self.sock.connect((self.ip, self.port))
            
            # 1. Send Handshake
            self.send_handshake()
            
            # 2. Receive Handshake
            response = self.receive_handshake()
            if not response:
                print("Handshake failed.")
                return
            
            print("Handshake successful! Listening for messages...")
            
            # 3. Start the Message Loop
            self.message_loop()
            
        except Exception as e:
            print(f"Connection error: {e}")
        finally:
            self.sock.close()

    def send_handshake(self):
        # Protocol string length (19) + String + 8 reserved bytes + Info Hash + Peer ID
        # B = unsigned char (1 byte)
        # 19s = string of 19 bytes
        # 8x = 8 pad bytes (0)
        # 20s = string of 20 bytes
        msg = struct.pack('>B19s8x20s20s', 19, b'BitTorrent protocol', self.info_hash, self.peer_id)
        self.sock.send(msg)

    def receive_handshake(self):
        # Handshake is always 68 bytes
        response = self.sock.recv(68)
        if len(response) < 68:
            return None
        
        # Verify the info hash matches what we expect
        # Response structure is the same: 1 byte len + 19 byte str + 8 byte reserved + 20 byte hash + 20 byte ID
        peer_info_hash = response[28:48] 
        if peer_info_hash != self.info_hash:
            print(f"Error: Peer sent wrong Info Hash. Expected {self.info_hash.hex()} got {peer_info_hash.hex()}")
            return None
            
        return response

    def request_next_block(self):
        if self.am_choked:
            return 
        
        # Check if we have finished all pieces
        if self.current_piece >= self.total_pieces:
            return 

        # Check if peer actuall Has this piece
        if self.current_piece not in self.available_pieces:
            print(f"Peer doesn't have Piece {self.current_piece}. Waiting...")
            return 

        # Send the request
        self.send_request(self.current_piece, self.current_offset, self.BLOCK_SIZE) 


    def message_loop(self):
        while True:
            # Receive data and add to buffer
            try:
                data = self.sock.recv(4096)
                if not data:
                    break # Connection closed
                self.buffer += data
                print("Received data:", self.buffer)
            except socket.timeout:
                # Keep alive logic would go here
                continue

            # Process buffer
            self.parse_messages()

    def parse_messages(self):
        # A message is: Length (4 bytes) + ID (1 byte) + Payload (Length - 1 bytes)
        
        while len(self.buffer) >= 4:
            # 1. Read the length (first 4 bytes)
            # >I = Big Endian Unsigned Integer
            msg_len = struct.unpack('>I', self.buffer[0:4])[0]

            # Special Case: Keep-Alive message has length 0 and no ID/Payload
            if msg_len == 0:
                print("Received: Keep-Alive")
                self.buffer = self.buffer[4:]
                continue

            # 2. Do we have the full message?
            if len(self.buffer) < 4 + msg_len:
                break # Wait for more data

            # 3. Extract the Message ID and Payload
            msg_id = self.buffer[4] # The 5th byte is the ID
            payload = self.buffer[5 : 4 + msg_len]

            # 4. Handle the specific message
            self.handle_message(msg_id, payload)

            # 5. Remove processed message from buffer
            self.buffer = self.buffer[4 + msg_len:]

    def handle_message(self, msg_id, payload):
        # Standard BitTorrent Message IDs
        if msg_id == 0:
            print("Received: Choke (Peer won't upload to us)")
            self.am_choked = True

        elif msg_id == 1:
            print("Received: Unchoke. Ready to request!")
            self.am_choked = False
            self.request_next_block()

        elif msg_id == 4:
            # Have message: payload contains the piece index they have
            piece_index = struct.unpack('>I', payload)[0]
            print(f"Received: Have piece {piece_index}")
            self.available_pieces.add(piece_index)

            if piece_index == self.current_piece:
                self.request_next_block()

        elif msg_id == 5:
            print("Received: Bitfield (Map of all pieces they have)")
            self.parse_bitfield(payload)
            print(f"Peer has {len(self.available_pieces)} pieces.")
        elif msg_id == 7:
            # Piece Message: Index(4) + Begin(4) + Data(Variable)
            piece_index = struct.unpack('>I', payload[0:4])[0]
            begin_offset = struct.unpack('>I', payload[4:8])[0]
            block_data = payload[8:]
            
            print(f"SUCCESS! Received Block: Piece {piece_index} @ {begin_offset}")
            print(f"Data Length: {len(block_data)} bytes")
            print(f"First 20 bytes: {block_data[:20]}")

            # Write to disk!
            self.file_manager.write_block(piece_index, begin_offset, block_data)

            # 3. ADVANCE THE CURSOR
            self.current_offset += len(block_data)

            if self.current_offset >= self.piece_length:
                print(f"--- Finished Piece {self.current_piece} ---")
                self.current_piece += 1
                self.current_offset = 0

            # 5. TRIGGER NEXT REQUEST
            self.request_next_block()   
        else:
            print(f"Received: Message ID {msg_id}")

    def parse_bitfield(self, payload):
        self.available_pieces.clear() # Reset
        
        # Iterate through every byte in the payload
        for i, byte_val in enumerate(payload):
            # For each byte, check all 8 bits
            for bit_rank in range(8):
                # Check if the bit at 'bit_rank' is set (1)
                # We check from left (high) to right (low)
                # 1 << 7 is 10000000
                # 1 << 6 is 01000000
                mask = 1 << (7 - bit_rank)
                
                if byte_val & mask:
                    # Calculate the actual piece index
                    piece_index = (i * 8) + bit_rank
                    self.available_pieces.add(piece_index)
                    
    def send_request(self, piece_index, block_offset, block_length):
        # ID = 6 (Request)
        # Payload = Index (4 bytes) + Begin (4 bytes) + Length (4 bytes)
        req_payload = struct.pack('>III', piece_index, block_offset, block_length)
        
        # Message Length = 1 (ID) + 12 (Payload) = 13
        msg = struct.pack('>IB', 13, 6) + req_payload
        self.sock.send(msg)
        print(f"Sent Request: Piece {piece_index}, Offset {block_offset}, Len {block_length}")

# --- Usage Mockup ---
# To test this, you need a real Info Hash from a real .torrent file
if __name__ == "__main__":
    PIECE_LENGTH = 256 * 1024  # 256KB
    TOTAL_PIECES = 8           # We want 8 pieces total
    TOTAL_FILE_SIZE = PIECE_LENGTH * TOTAL_PIECES
    OUTPUT_FILE = "downloaded_file.dat"

    # Create the empty file first
    create_empty_file(OUTPUT_FILE, TOTAL_FILE_SIZE)

    # Initialize FileManager
    file_manager = FileManager(OUTPUT_FILE, PIECE_LENGTH)
    
    # Use the SAME Info Hash as the mock peer
    fake_info_hash = b'12345678901234567890'
    my_peer_id = b'-PC0001-999999999999'
    
    # Connect to localhost
    peer = PeerConnection('127.0.0.1', 6881, fake_info_hash, my_peer_id, file_manager, TOTAL_PIECES, PIECE_LENGTH)
    peer.connect()