import socket
import json
import threading
import signal
import sys
from typing import Dict, Any
from completion import generate_completions

class TCPServer:
    def __init__(self, host='localhost', port=3000):
        self.host = host
        self.port = port
        self.server_socket = None
        self.running = False
        self.active_connections = []
        
        # Set up signal handling
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

    def signal_handler(self, signum, frame):
        print(f"\nReceived signal {signum}, shutting down...")
        self.shutdown()

    def handle_client(self, conn: socket.socket, addr: tuple):
        print(f"Connected by {addr}")
        self.active_connections.append(conn)
        try:
            while self.running:
                data = conn.recv(4096)
                if not data:
                    break
                
                try:
                    request = json.loads(data.decode('utf-8'))
                    response = generate_completions(request)
                    conn.sendall((json.dumps(response) + '\n').encode('utf-8'))
                except json.JSONDecodeError as e:
                    error_response = {"error": f"Invalid JSON: {str(e)}"}
                    conn.sendall((json.dumps(error_response) + '\n').encode('utf-8'))
                    
        except ConnectionResetError:
            print(f"Client {addr} disconnected unexpectedly")
        finally:
            conn.close()
            self.active_connections.remove(conn)

    def start(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen()
        self.running = True
        
        print(f"Server listening on {self.host}:{self.port}")
        try:
            while self.running:
                try:
                    conn, addr = self.server_socket.accept()
                    thread = threading.Thread(target=self.handle_client, args=(conn, addr))
                    thread.daemon = True  # Daemon threads will exit when main exits
                    thread.start()
                except socket.timeout:
                    continue
        except Exception as e:
            if self.running:  # Only print if not shutting down
                print(f"Server error: {str(e)}")
        finally:
            self.shutdown()

    def shutdown(self):
        print("Shutting down server...")
        self.running = False
        
        # Close all active connections
        for conn in self.active_connections:
            try:
                conn.shutdown(socket.SHUT_RDWR)
                conn.close()
            except:
                pass
        
        # Close server socket
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        
        print("Server shutdown complete")
        sys.exit(0)


from dotenv import load_dotenv
import os
if __name__ == '__main__':
    load_dotenv()
    server_host = os.getenv('SERVER_HOST', 'localhost')
    server_port = int(os.getenv('SERVER_PORT', '3000'))
    server = TCPServer(host=server_host, port=server_port)
    server.start()