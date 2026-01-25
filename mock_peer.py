import socket
import struct
import time

HOST = '127.0.0.1'
PORT = 6881
EXPECTED_INFO_HASH = b'12345678901234567890' 
MY_PEER_ID = b'-MK0001-123456789012'

def start_mock_peer():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(1)
    
    print(f"[MOCK PEER] Listening on {HOST}:{PORT}...")
    conn, addr = server.accept()
    
    # 1. Handshake Handling
    data = conn.recv(68)
    print(f"[MOCK PEER] Handshake received.")
    response_handshake = struct.pack('>B19s8x20s20s', 19, b'BitTorrent protocol', EXPECTED_INFO_HASH, MY_PEER_ID)
    conn.send(response_handshake)

    # 2. Send Bitfield (All pieces)
    conn.send(struct.pack('>IBB', 2, 5, 0xFF))

    # 3. Send Unchoke
    conn.send(struct.pack('>IB', 1, 1))

    # 4. LOOP: Listen for Requests
    while True:
        try:
            # Read header (4 bytes length)
            header = conn.recv(4)
            if not header: break
            print("Header received.", header)

            msg_len = struct.unpack('>I', header)[0]
            print("msg_len", msg_len)
            # Read rest of message
            msg_body = conn.recv(msg_len)
            
            msg_id = msg_body[0]
            
            if msg_id == 6: # Request Message
                # Parse Payload: Index, Begin, Length
                idx, begin, length = struct.unpack('>III', msg_body[1:])
                print(f"[MOCK PEER] Client requested: Index={idx}, Begin={begin}, Len={length}")
                
                # Generate Fake Data (just a bunch of 'A's)
                fake_data = b'A' * length
                
                # Construct Piece Message (ID 7)
                # Header = 4 bytes length
                # Body = ID(1) + Index(4) + Begin(4) + Data(N)
                response_len = 9 + length
                response_header = struct.pack('>I', response_len)
                response_body = struct.pack('>BII', 7, idx, begin) + fake_data
                
                conn.send(response_header + response_body)
                print(f"[MOCK PEER] Sent {length} bytes of data back.")
                
        except Exception as e:
            print(f"[MOCK PEER] Error: {e}")
            break

    conn.close()

if __name__ == "__main__":
    start_mock_peer()