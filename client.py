import socket
import struct
import time

class PeerConnection:
    def __init__(self, ip, port, info_hash, peer_id):
        self.ip = ip
        self.port = port
        self.info_hash = info_hash # Expecting bytes, not hex string
        self.peer_id = peer_id     # Expecting bytes
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(5)    # Don't hang forever
        self.buffer = b""          # Our stream buffer

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
        elif msg_id == 1:
            print("Received: Unchoke (We can request data!)")
        elif msg_id == 4:
            # Have message: payload contains the piece index they have
            piece_index = struct.unpack('>I', payload)[0]
            print(f"Received: Have piece {piece_index}")
        elif msg_id == 5:
            print("Received: Bitfield (Map of all pieces they have)")
        elif msg_id == 7:
            print("Received: Piece Data! (We got a block)")
        else:
            print(f"Received: Message ID {msg_id}")

# --- Usage Mockup ---
# To test this, you need a real Info Hash from a real .torrent file
if __name__ == "__main__":
    # Use the SAME Info Hash as the mock peer
    fake_info_hash = b'12345678901234567890'
    my_peer_id = b'-PC0001-999999999999'
    
    # Connect to localhost
    peer = PeerConnection('127.0.0.1', 6881, fake_info_hash, my_peer_id)
    peer.connect()