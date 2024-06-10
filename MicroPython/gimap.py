import socket

DEFAULT_TIMEOUT = 10 #sec
CRLF = '\r\n'
class IMAP:
    def _new_tag(self):
        tag = f'A{self.tag_num}'
        self.tag_num += 1
        return tag
    
    def __init__(self, host, port, ssl=False):
        self.tag_num = 1
        addr = socket.getaddrinfo(host, port)[0][-1]
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(DEFAULT_TIMEOUT)
        sock.connect(addr)
        if ssl:
            import ssl
            sock = ssl.wrap_socket(sock)
        code = sock.read(4).decode().split(' ')[-1]
        print(host + ' ' + code)
        print(sock.readline().decode())
        if "OK" not in code:
            raise Exception("Eroare la conectare")
        self._sock=sock
            
    def login(self, username, password):
        self.username = username
        self.tag = self._new_tag()
        cmd = self.tag + ' LOGIN ' + self.username + ' ' + password + CRLF
        self._sock.write(cmd)
        response = self._sock.read(13).decode().split()[-1]
        #print(response) #CAPABILITY
        if "CAPABILITY" not in response:
            raise Exception("Eroare la log in")
        self._sock.readline()
        response = self._sock.readline()
        if 'authenticated (Success)' not in response:
            raise Exception("Erroare la log in")
        else:
            print("Success la log in")
        
    def list(self):
        self.mailboxes=[]
        self.tag = self._new_tag()
        cmd = self.tag + ' LIST ' + '\"\" \"*\"' + CRLF
        self._sock.write(cmd)
        response = self._sock.readline().decode()
        if "LIST" not in response:
            raise Exception("Eroare la LIST")
        while "LIST" in response:
            first_quote_index = response.find('"')
            first_quote_index = response.find('"', first_quote_index + 1)
            first_quote_index = response.find('"', first_quote_index + 1)
            second_quote_index = response.find('"', first_quote_index + 1)
            mailbox_name = response[first_quote_index + 1:second_quote_index]
            self.mailboxes.append(mailbox_name)
            response = self._sock.readline().decode()
            #print(response)
        print("mailboxu-uri: " + str(self.mailboxes))
            
    def select(self, mailbox):
        self.mailbox=mailbox
        if self.mailbox not in self.mailboxes:
            raise Exception("Mailboxul nu exista")
        self.tag= self._new_tag()
        cmd = self.tag + ' SELECT ' + mailbox + CRLF
        self._sock.write(cmd)
        response = self._sock.readline().decode()
        while "EXISTS" not in response:
            response = self._sock.readline().decode()
        print(response)
        no_mails = response[2:].split(" ")
        no_mails=int(no_mails[0])
        response = self._sock.readline().decode()
        while mailbox + " selected. (Success)" not in response:
            response = self._sock.readline().decode()
        if mailbox + " selected. (Success)" in response:
            print(self.mailbox + " selectat")
        return no_mails
    
    def fetch(self, index):
        self.tag = self._new_tag()
        cmd = self.tag + ' FETCH ' + str(index) + ' ' + "BODY[]" + CRLF
        self._sock.write(cmd)
        #for i in range (32):
            #   if self._sock.readline() is type(None):
            #response = self._sock.readline()
            #print(response)
         #      print("s")
        print("Fetch din mesajul " + str(index))
        while True:
            response = self._sock.readline().decode()
            #print(response)
            #if response == b'\r\n':
            #   pass
            if "Date:" in response:
                data = response[6:]
            if "From:" in response:
                exp = response[5:]
            if "Subject:" in response:
                subiect = response[8:]
            #if "Content-Type" in response:
                mesaj = ""
                response = self._sock.readline().decode()
                mesaj = mesaj + response
                while True:
                    response = self._sock.readline().decode()
                    #print(response)
                    if ")\r\n" in response:
                        print("Mesaj finalizat")
                        break
                    mesaj = mesaj + response
            if self.tag in response[0:4]:
                print("Fetch done")
                break
        #print("________________________________________")
        #print(exp)
        #print(subiect)
        #print(data)
        #print(mesaj)                   
        return exp, subiect, data, mesaj
        
