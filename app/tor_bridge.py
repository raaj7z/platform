import socket
import subprocess
import threading
import sys
import os
import time

def forward_stream(source_read, target_write):
    try:
        while True:
            data = source_read(4096)
            if not data:
                break
            target_write(data)
    except Exception:
        pass

def handle_client(client_sock):
    # Ensure WSL Tor is running
    cmd = [
        "wsl", "python3", "-c",
        "import socket, sys, threading\n"
        "s = socket.socket()\n"
        "s.connect(('127.0.0.1', 9050))\n"
        "def r():\n"
        "  try:\n"
        "    while True:\n"
        "      d = s.recv(4096)\n"
        "      if not d: break\n"
        "      sys.stdout.buffer.write(d)\n"
        "      sys.stdout.buffer.flush()\n"
        "  except: pass\n"
        "threading.Thread(target=r, daemon=True).start()\n"
        "try:\n"
        "  while True:\n"
        "    d = sys.stdin.buffer.read1(4096) if hasattr(sys.stdin.buffer, 'read1') else sys.stdin.buffer.read(4096)\n"
        "    if not d: break\n"
        "    s.sendall(d)\n"
        "except: pass\n"
    ]
    try:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        
        t1 = threading.Thread(target=forward_stream, args=(client_sock.recv, proc.stdin.write), daemon=True)
        t2 = threading.Thread(target=forward_stream, args=(proc.stdout.read, client_sock.sendall), daemon=True)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        try:
            proc.kill()
        except Exception:
            pass
    except Exception:
        pass
    finally:
        try:
            client_sock.close()
        except Exception:
            pass

def ensure_tor_started():
    """Ensure WSL Tor daemon and bridge are running."""
    # First start Tor in WSL
    try:
        subprocess.run(["wsl", "sudo", "service", "tor", "start"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
    except Exception:
        pass

def main():
    ensure_tor_started()
    try:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(('127.0.0.1', 9050))
        server.listen(20)
        print("Tor Bridge listening on Windows 127.0.0.1:9050...")
        while True:
            client, _ = server.accept()
            threading.Thread(target=handle_client, args=(client,), daemon=True).start()
    except OSError:
        # Already running and listening on 127.0.0.1:9050
        print("Tor Bridge already active on 127.0.0.1:9050")

if __name__ == "__main__":
    main()
