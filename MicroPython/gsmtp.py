import socket

DEFAULT_TIMEOUT = 10 #sec
CRLF = '\r\n'

class SMTP:
    def command(self, command_string):
        self._sock.write(command_string + '\r\n')
        response = []
        next = True
        while next:
            code = self._sock.read(3)
            next = self._sock.read(1) == b'-' #pentru raspunsuri multiline
            response.append(self._sock.readline().strip().decode())
        return int(code), response
    
    def __init__(self, host, port, ssl=False):
        addr = socket.getaddrinfo(host, port)[0][-1]
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(DEFAULT_TIMEOUT)
        sock.connect(addr)
        if ssl:
            import ssl
            sock = ssl.wrap_socket(sock)
        self._sock = sock
        line = self._sock.readline().decode()
        code = int(line[0:3])
        print(code)
        print(line)
        if code != 220:
            raise Exception("Eroare la conectare")
        
    def login(self, username, password):
        self.username=username
        code, response = self.command('EHLO 127.0.0.1')
        print(code)
        print(response)
        
        auth_methods = None
        for resp in response:
            if resp[:4].upper() == 'AUTH':
                auth_methods = resp[4:].split()
        print(auth_methods)
        if auth_methods == None:
            raise Exception("Nu exista metode de autentificare")
        
        from binascii import b2a_base64 as b64
        if 'LOGIN' in auth_methods:
            code, response = self.command("%s %s %s" % ('AUTH', 'LOGIN' , b64(username)[:-1].decode()))
            print(code)
            print(response)
            if code != 334:
                raise Exception("Username gresit")
            code, resp = self.command(b64(password)[:-1].decode())
            print(code)
            print(response)
            if code != 235:
                raise Exception("Parola gresita")
            
    def write(self, content):
        self._sock.write(content)
        
    def to(self, address):
        mail_from = self.username   
        code, response = self.command('EHLO 127.0.0.1')
        code, resp = self.command('MAIL FROM: <%s>' % mail_from)
        if code != 250:
            raise Exception("Eroare expeditor")
        
        if isinstance(address, str):
            address = [address]
        for addrs in address:
            code, resp = self.command('RCPT TO: <%s>' % addrs)
            print(code)
            print(resp)
            if code!=250 and code!=251:
                raise Exception("Eroare la destinatarul " + addrs)
        
        code, resp = self.command('DATA')
        if code != 354:
            raise Exception("Data refuzata")
        
    def send(self, content=''):
        if content:
            self.write(content)
        self._sock.write('\r\n.\r\n')
        response = self._sock.readline()
        print(response)
        
    def quit(self):
        self.command("QUIT")
        self._sock.close()
