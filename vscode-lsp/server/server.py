# server.py
import socket
import json
import threading
import signal
import sys
from typing import Dict, Any, Tuple

# Import the completion logic
from completion import generate_completions

class TCPServer:
    def __init__(self, host='localhost', port=3000):
        self.host = host
        self.port = port
        self.server_socket = None
        self.running = False
        self.active_connections = []
        self.BUFF_SIZE = 4096 # Buffer size for socket receive operations
        self.CLIENT_SOCKET_TIMEOUT = 5.0 # Timeout for client socket receive operations (in seconds)

        # Set up signal handling for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

    def signal_handler(self, signum, frame):
        """Handles signals for graceful shutdown."""
        print(f"\nReceived signal {signum}, shutting down...")
        self.shutdown()

    def _read_lsp_message(self, conn: socket.socket) -> Dict[str, Any] | None:
        """
        Reads a single LSP message from the socket.
        LSP messages are framed with Content-Length and Content-Type headers.
        """
        headers = {}
        content_length = 0
        
        # Read headers line by line until an empty line is encountered (signifying end of headers)
        try:
            while True:
                line_bytes = b''
                # Read byte by byte until CRLF or timeout, to handle line buffering
                while True:
                    byte = conn.recv(1)
                    if not byte: # Connection closed
                        print("Connection closed while reading header byte.")
                        return None
                    line_bytes += byte
                    if line_bytes.endswith(b'\r\n'):
                        break
                
                line = line_bytes.decode('utf-8').strip()
                
                if not line: # Empty line signifies end of headers
                    break
                
                if ':' in line:
                    key, value = line.split(':', 1)
                    headers[key.strip()] = value.strip()
                    if key.strip().lower() == 'content-length':
                        try:
                            content_length = int(value.strip())
                        except ValueError:
                            print(f"Invalid Content-Length header: {value.strip()}")
                            return None
                else:
                    # Malformed header, or unexpected line
                    print(f"Malformed header line: {line}")
                    return None
        except socket.timeout:
            print("Socket timeout while reading LSP headers.")
            return None
        except Exception as e:
            print(f"Error reading LSP headers: {e}")
            return None
        
        if content_length == 0:
            print("Content-Length header not found or is 0.")
            return None

        # Read the JSON payload
        payload_bytes = b''
        try:
            while len(payload_bytes) < content_length:
                chunk = conn.recv(content_length - len(payload_bytes))
                if not chunk:
                    # Connection closed before full payload received
                    print("Connection closed while reading payload.")
                    return None
                payload_bytes += chunk
        except socket.timeout:
            print("Socket timeout while reading LSP payload.")
            return None
        except Exception as e:
            print(f"Error reading LSP payload: {e}")
            return None
        
        try:
            return json.loads(payload_bytes.decode('utf-8'))
        except json.JSONDecodeError as e:
            print(f"Failed to decode JSON payload: {e}")
            return None
        except UnicodeDecodeError as e:
            print(f"Failed to decode payload bytes to UTF-8: {e}")
            return None

    def _write_lsp_message(self, conn: socket.socket, response: Dict[str, Any]):
        """
        Writes an LSP response message to the socket with proper framing.
        """
        json_payload = json.dumps(response).encode('utf-8')
        content_length = len(json_payload)
        
        # Construct LSP headers
        headers = [
            f"Content-Length: {content_length}",
            "Content-Type: application/json"
        ]
        
        # Join headers with CRLF and add final CRLF for header/content separation
        message = "\r\n".join(headers).encode('utf-8') + b"\r\n\r\n" + json_payload
        
        try:
            conn.sendall(message)
        except Exception as e:
            print(f"Error sending LSP message: {e}")

    def handle_client(self, conn: socket.socket, addr: Tuple[str, int]):
        """Handles a single client connection."""
        print(f"Connected by {addr}")
        self.active_connections.append(conn)
        
        # Set a timeout for individual client socket receive operations
        conn.settimeout(self.CLIENT_SOCKET_TIMEOUT)

        try:
            while self.running:
                # Read incoming LSP request
                request = self._read_lsp_message(conn)
                if request is None:
                    # Client disconnected or message reading failed/timed out
                    break
                
                # Process the request and generate response
                response = generate_completions(request)
                
                # Send the LSP response back to the client
                self._write_lsp_message(conn, response)
                
        except ConnectionResetError:
            print(f"Client {addr} disconnected unexpectedly")
        except socket.timeout:
            print(f"Client {addr} timed out during communication.")
        except Exception as e:
            # Catch any other unexpected errors during client handling
            print(f"Error handling client {addr}: {e}")
        finally:
            print(f"Client {addr} connection closed.")
            try:
                conn.shutdown(socket.SHUT_RDWR)
                conn.close()
            except OSError as e:
                # Ignore errors if socket is already closed or not connected
                if e.errno not in (107, 57): # 107: Transport endpoint is not connected, 57: Socket is not connected (macOS)
                    print(f"Error closing client socket: {e}")
            except Exception as e:
                print(f"Unexpected error during client socket close: {e}")
            finally:
                # Ensure connection is removed from active list
                if conn in self.active_connections:
                    self.active_connections.remove(conn)

    def start(self):
        """Starts the TCP server, listening for incoming connections."""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        
        # Set a timeout on accept() to allow the server to check self.running periodically
        self.server_socket.settimeout(1.0) # 1 second timeout

        self.server_socket.listen()
        self.running = True
        
        print(f"Server listening on {self.host}:{self.port}")
        try:
            while self.running:
                try:
                    conn, addr = self.server_socket.accept()
                    # Create a new thread for each client connection
                    thread = threading.Thread(target=self.handle_client, args=(conn, addr))
                    thread.daemon = True  # Daemon threads exit when the main program exits
                    thread.start()
                except socket.timeout:
                    # Timeout occurred, loop continues to check self.running
                    continue
                except OSError as e:
                    # Handle specific OS errors, e.g., if socket is closed while waiting for accept
                    if self.running: # Only print if not explicitly shutting down
                        print(f"Accept error: {e}")
                    break # Exit loop if a critical socket error occurs
                except Exception as e:
                    if self.running:
                        print(f"Server start error: {str(e)}")
                    break # Exit loop on unexpected errors
        finally:
            self.shutdown()

    def shutdown(self):
        """Initiates a graceful shutdown of the server."""
        print("Shutting down server...")
        self.running = False
        
        # Close all active client connections first
        # Create a copy of the list to avoid issues with modification during iteration
        for conn in list(self.active_connections):
            try:
                conn.shutdown(socket.SHUT_RDWR)
                conn.close()
            except Exception as e:
                print(f"Error closing active connection: {e}")
        self.active_connections.clear() # Clear the list after attempting to close all

        # Close the main server listening socket
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception as e:
                print(f"Error closing server socket: {e}")
            finally:
                self.server_socket = None # Clear reference
        
        print("Server shutdown complete")
        sys.exit(0) # Exit the program

# --- Main execution block ---
from dotenv import load_dotenv
import os

if __name__ == '__main__':
    load_dotenv() # Load environment variables from .env file
    server_host = os.getenv('SERVER_HOST', 'localhost')
    server_port = int(os.getenv('SERVER_PORT', '3000'))
    
    server = TCPServer(host=server_host, port=server_port)
    server.start()