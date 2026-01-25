import socket
import struct

# Configuration
HOST = '127.0.0.1'
PORT = 6881
# A fake Info Hash (must match what the client sends)
EXPECTED_INFO_HASH = b'12345678901234567890' 
MY_PEER_ID = b'-MK0001-123456789012'

def start_mock_peer():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST, PORT))
    server.listen(1)
    
    print(f"[MOCK PEER] Listening on {HOST}:{PORT}...")
    
    conn, addr = server.accept()
    print(f"[MOCK PEER] Connection from {addr}")
    
    # 1. Receive Handshake
    data = conn.recv(68)
    if not data:
        return
        
    print(f"[MOCK PEER] Received {len(data)} bytes handshake.")
    
    # Parse just enough to verify
    protocol_len = data[0]
    pstr = data[1:20]
    info_hash = data[28:48]
    
    print(f"[MOCK PEER] Protocol: {pstr}")
    print(f"[MOCK PEER] Client Info Hash: {info_hash}")

    # 2. Send Handshake Back
    # Structure: len(19) + "BitTorrent protocol" + 8 reserved + info_hash + peer_id
    response_handshake = struct.pack('>B19s8x20s20s', 19, b'BitTorrent protocol', EXPECTED_INFO_HASH, MY_PEER_ID)
    conn.send(response_handshake)
    print("[MOCK PEER] Sent Handshake.")

    # 3. Send "Bitfield" Message (ID = 5)
    # Let's pretend we have 8 pieces, and we have them all (11111111 in binary = 255 or 0xFF)
    # Length = 1 (ID) + 1 (Payload) = 2
    # ID = 5
    # Payload = 0xFF
    bitfield_msg = struct.pack('>IBB', 2, 5, 0xFF)
    # bitfield_msg = struct.pack('>IBB', 2, 5, 0xAA)
    conn.send(bitfield_msg)
    print("[MOCK PEER] Sent Bitfield (I have all pieces).")

    # 4. Send "Unchoke" Message (ID = 1)
    # Length = 1
    # ID = 1
    unchoke_msg = struct.pack('>IB', 1, 1)
    conn.send(unchoke_msg)
    print("[MOCK PEER] Sent Unchoke.")

    # Keep connection open for a moment so client can read
    import time
    time.sleep(2)
    conn.close()
    print("[MOCK PEER] Closing connection.")

if __name__ == "__main__":
    start_mock_peer()