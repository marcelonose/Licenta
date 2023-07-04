"uimaplib - imaplib for MicroPython on RPi Pico W and other MCU's"

__version__ = "0.1"

#imported libraries

import re


try:
    import ssl
    HAVE_SSL = True
except ImportError:
    HAVE_SSL = False


#		Globals
CRLF = b'\r\n'
Debug = 0
IMAP4_PORT = 143
IMAP4_SSL_PORT = 993
AllowedVersions = ('IMAP4REV1', 'IMAP4')        # Most recent first

# Maximal line length when calling readline(). This is to prevent
# reading arbitrary length lines. RFC 3501 and 2060 (IMAP 4rev1)
# don't specify a line length. RFC 2683 suggests limiting client
# command lines to 1000 octets and that servers should be prepared
# to accept command lines up to 8000 octets, so we used to use 10K here.
# In the modern world (eg: gmail) the response to, for example, a
# search command can be quite large, so we now use 1M.
_MAXLINE = 1000000


#   	Commands in version 0.1 none implemented

Commands = {
        # name            valid states
        'APPEND':       ('AUTH', 'SELECTED'),
        'AUTHENTICATE': ('NONAUTH',),
        'CAPABILITY':   ('NONAUTH', 'AUTH', 'SELECTED', 'LOGOUT'),
        'CHECK':        ('SELECTED',),
        'CLOSE':        ('SELECTED',),
        'COPY':         ('SELECTED',),
        'CREATE':       ('AUTH', 'SELECTED'),
        'DELETE':       ('AUTH', 'SELECTED'),
        'DELETEACL':    ('AUTH', 'SELECTED'),
        'ENABLE':       ('AUTH', ),
        'EXAMINE':      ('AUTH', 'SELECTED'),
        'EXPUNGE':      ('SELECTED',),
        'FETCH':        ('SELECTED',),
        'GETACL':       ('AUTH', 'SELECTED'),
        'GETANNOTATION':('AUTH', 'SELECTED'),
        'GETQUOTA':     ('AUTH', 'SELECTED'),
        'GETQUOTAROOT': ('AUTH', 'SELECTED'),
        'MYRIGHTS':     ('AUTH', 'SELECTED'),
        'LIST':         ('AUTH', 'SELECTED'),
        'LOGIN':        ('NONAUTH',),
        'LOGOUT':       ('NONAUTH', 'AUTH', 'SELECTED', 'LOGOUT'),
        'LSUB':         ('AUTH', 'SELECTED'),
        'MOVE':         ('SELECTED',),
        'NAMESPACE':    ('AUTH', 'SELECTED'),
        'NOOP':         ('NONAUTH', 'AUTH', 'SELECTED', 'LOGOUT'),
        'PARTIAL':      ('SELECTED',),                                  # NB: obsolete
        'PROXYAUTH':    ('AUTH',),
        'RENAME':       ('AUTH', 'SELECTED'),
        'SEARCH':       ('SELECTED',),
        'SELECT':       ('AUTH', 'SELECTED'),
        'SETACL':       ('AUTH', 'SELECTED'),
        'SETANNOTATION':('AUTH', 'SELECTED'),
        'SETQUOTA':     ('AUTH', 'SELECTED'),
        'SORT':         ('SELECTED',),
        'STARTTLS':     ('NONAUTH',),
        'STATUS':       ('AUTH', 'SELECTED'),
        'STORE':        ('SELECTED',),
        'SUBSCRIBE':    ('AUTH', 'SELECTED'),
        'THREAD':       ('SELECTED',),
        'UID':          ('SELECTED',),
        'UNSUBSCRIBE':  ('AUTH', 'SELECTED'),
        'UNSELECT':     ('SELECTED',),
        }


#       Patterns to match server responses

Continuation = re.compile(br'\+( (?P<data>.*))?')
Flags = re.compile(br'.*FLAGS \((?P<flags>[^\)]*)\)')
InternalDate = re.compile(br'.*INTERNALDATE "'
        br'(?P<day>[ 0123][0-9])-(?P<mon>[A-Z][a-z][a-z])-(?P<year>[0-9][0-9][0-9][0-9])'
        br' (?P<hour>[0-9][0-9]):(?P<min>[0-9][0-9]):(?P<sec>[0-9][0-9])'
        br' (?P<zonen>[-+])(?P<zoneh>[0-9][0-9])(?P<zonem>[0-9][0-9])'
        br'"')
# Literal is no longer used; kept for backward compatibility.
Literal = re.compile(br'.*{(?P<size>\d+)}$', re.ASCII)
MapCRLF = re.compile(br'\r\n|\r|\n')
# We no longer exclude the ']' character from the data portion of the response
# code, even though it violates the RFC.  Popular IMAP servers such as Gmail
# allow flags with ']', and there are programs (including imaplib!) that can
# produce them.  The problem with this is if the 'text' portion of the response
# includes a ']' we'll parse the response wrong (which is the point of the RFC
# restriction).  However, that seems less likely to be a problem in practice
# than being unable to correctly parse flags that include ']' chars, which
# was reported as a real-world problem in issue #21815.
Response_code = re.compile(br'\[(?P<type>[A-Z-]+)( (?P<data>.*))?\]')
Untagged_response = re.compile(br'\* (?P<type>[A-Z-]+)( (?P<data>.*))?')
# Untagged_status is no longer used; kept for backward compatibility
Untagged_status = re.compile(
    br'\* (?P<data>\d+) (?P<type>[A-Z-]+)( (?P<data2>.*))?', re.ASCII)
# We compile these in _mode_xxx.
_Literal = br'.*{(?P<size>\d+)}$'
_Untagged_status = br'\* (?P<data>\d+) (?P<type>[A-Z-]+)( (?P<data2>.*))?'


class IMAP4:

    r"""IMAP4 client class.
    Instantiate with: IMAP4([host[, port[, timeout=None]]])
            host - host's name (default: localhost);
            port - port number (default: standard IMAP4 port).
            timeout - socket timeout (default: None)
                      If timeout is not given or is None,
                      the global default socket timeout is used
    All IMAP4rev1 commands are supported by methods of the same
    name (in lowercase).
    All arguments to commands are converted to strings, except for
    AUTHENTICATE, and the last argument to APPEND which is passed as
    an IMAP4 literal.  If necessary (the string contains any
    non-printing characters or white-space and isn't enclosed with
    either parentheses or double quotes) each string is quoted.
    However, the 'password' argument to the LOGIN command is always
    quoted.  If you want to avoid having an argument string quoted
    (eg: the 'flags' argument to STORE) then enclose the string in
    parentheses (eg: "(\Deleted)").
    Each command returns a tuple: (type, [data, ...]) where 'type'
    is usually 'OK' or 'NO', and 'data' is either the text from the
    tagged response, or untagged results from command. Each 'data'
    is either a string, or a tuple. If a tuple, then the first part
    is the header of the response, and the second part contains
    the data (ie: 'literal' value).
    Errors raise the exception class <instance>.error("<reason>").
    IMAP4 server errors raise <instance>.abort("<reason>"),
    which is a sub-class of 'error'. Mailbox status changes
    from READ-WRITE to READ-ONLY raise the exception class
    <instance>.readonly("<reason>"), which is a sub-class of 'abort'.
    "error" exceptions imply a program error.
    "abort" exceptions imply the connection should be reset, and
            the command re-tried.
    "readonly" exceptions imply the command should be re-tried.
    Note: to use this module, you must read the RFCs pertaining to the
    IMAP4 protocol, as the semantics of the arguments to each IMAP4
    command are left to the invoker, not to mention the results. Also,
    most IMAP servers implement a sub-set of the commands available here.
    """

    class error(Exception): pass    # Logical errors - debug required
    class abort(error): pass        # Service errors - close and retry
    class readonly(abort): pass     # Mailbox status changed to READ-ONLY

    def __init__(self, host='', port=IMAP4_PORT, timeout=None):
        self.debug = Debug
        self.state = 'LOGOUT'
        self.literal = None             # A literal argument to a command
        self.tagged_commands = {}       # Tagged commands awaiting response
        self.untagged_responses = {}    # {typ: [data, ...], ...}
        self.continuation_response = '' # Last continuation response
        self.is_readonly = False        # READ-ONLY desired state
        self.tagnum = 0
        self._tls_established = False
        self._mode_ascii()

       

    #       IMAP4 commands


    def append(self, mailbox, flags, date_time, message):
        """Append message to named mailbox.
        (typ, [data]) = <instance>.append(mailbox, flags, date_time, message)
                All args except `message' can be None.
        """


    def authenticate(self, mechanism, authobject):
        """Authenticate command - requires response processing.
        'mechanism' specifies which authentication mechanism is to
        be used - it must appear in <instance>.capabilities in the
        form AUTH=<mechanism>.
        'authobject' must be a callable object:
                data = authobject(response)
        It will be called to process server continuation responses; the
        response argument it is passed will be a bytes.  It should return bytes
        data that will be base64 encoded and sent to the server.  It should
        return None if the client abort response '*' should be sent instead.
        """


    def capability(self):
        """(typ, [data]) = <instance>.capability()
        Fetch capabilities list from server."""


    def check(self):
        """Checkpoint mailbox on server.
        (typ, [data]) = <instance>.check()
        """


    def close(self):
        """Close currently selected mailbox.
        Deleted messages are removed from writable mailbox.
        This is the recommended command before 'LOGOUT'.
        (typ, [data]) = <instance>.close()
        """
      


    def copy(self, message_set, new_mailbox):
        """Copy 'message_set' messages onto end of 'new_mailbox'.
        (typ, [data]) = <instance>.copy(message_set, new_mailbox)
        """


    def create(self, mailbox):
        """Create new mailbox.
        (typ, [data]) = <instance>.create(mailbox)
        """


    def delete(self, mailbox):
        """Delete old mailbox.
        (typ, [data]) = <instance>.delete(mailbox)
        """

    def deleteacl(self, mailbox, who):
        """Delete the ACLs (remove any rights) set for who on mailbox.
        (typ, [data]) = <instance>.deleteacl(mailbox, who)
        """

    def enable(self, capability):
        """Send an RFC5161 enable string to the server.
        (typ, [data]) = <instance>.enable(capability)
        """
      

    def expunge(self):
        """Permanently remove deleted items from selected mailbox.
        Generates 'EXPUNGE' response for each deleted message.
        (typ, [data]) = <instance>.expunge()
        'data' is list of 'EXPUNGE'd message numbers in order received.
        """
    


    def fetch(self, message_set, message_parts):
        """Fetch (parts of) messages.
        (typ, [data, ...]) = <instance>.fetch(message_set, message_parts)
        'message_parts' should be a string of selected parts
        enclosed in parentheses, eg: "(UID BODY[TEXT])".
        'data' are tuples of message part envelope and data.
        """
   


    def getacl(self, mailbox):
        """Get the ACLs for a mailbox.
        (typ, [data]) = <instance>.getacl(mailbox)
        """
  


    def getannotation(self, mailbox, entry, attribute):
        """(typ, [data]) = <instance>.getannotation(mailbox, entry, attribute)
        Retrieve ANNOTATIONs."""



    def getquota(self, root):
        """Get the quota root's resource usage and limits.
        Part of the IMAP4 QUOTA extension defined in rfc2087.
        (typ, [data]) = <instance>.getquota(root)
        """


    def getquotaroot(self, mailbox):
        """Get the list of quota roots for the named mailbox.
        (typ, [[QUOTAROOT responses...], [QUOTA responses]]) = <instance>.getquotaroot(mailbox)
        """



    def list(self, directory='""', pattern='*'):
        """List mailbox names in directory matching pattern.
        (typ, [data]) = <instance>.list(directory='""', pattern='*')
        'data' is list of LIST responses.
        """



    def login(self, user, password):
        """Identify client using plaintext password.
        (typ, [data]) = <instance>.login(user, password)
        NB: 'password' will be quoted.
        """



    def login_cram_md5(self, user, password):
        """ Force use of CRAM-MD5 authentication.
        (typ, [data]) = <instance>.login_cram_md5(user, password)
        """



    def _CRAM_MD5_AUTH(self, challenge):
        """ Authobject to use with CRAM-MD5 authentication. """



    def logout(self):
        """Shutdown connection to server.
        (typ, [data]) = <instance>.logout()
        Returns server 'BYE' response.
       


    def lsub(self, directory='""', pattern='*'):
        """List 'subscribed' mailbox names in directory matching pattern.
        (typ, [data, ...]) = <instance>.lsub(directory='""', pattern='*')
        'data' are tuples of message part envelope and data.
  

    def myrights(self, mailbox):
        """Show my ACLs for a mailbox (i.e. the rights that I have on mailbox).
        (typ, [data]) = <instance>.myrights(mailbox)
        """


    def namespace(self):
        """ Returns IMAP namespaces ala rfc2342
        (typ, [data, ...]) = <instance>.namespace()



    def noop(self):
        """Send NOOP command.
        (typ, [data]) = <instance>.noop()
        """



    def partial(self, message_num, message_part, start, length):
        """Fetch truncated part of a message.
        (typ, [data, ...]) = <instance>.partial(message_num, message_part, start, length)
        'data' is tuple of message part envelope and data.
  


    def proxyauth(self, user):
        """Assume authentication as "user".
        Allows an authorised administrator to proxy into any user's
        mailbox.
        (typ, [data]) = <instance>.proxyauth(user)
        """



    def rename(self, oldmailbox, newmailbox):
        """Rename old mailbox name to new.
        (typ, [data]) = <instance>.rename(oldmailbox, newmailbox)
        """


    def search(self, charset, *criteria):
        """Search mailbox for matching messages.
        (typ, [data]) = <instance>.search(charset, criterion, ...)
        'data' is space separated list of matching message numbers.
        If UTF8 is enabled, charset MUST be None.
        """
  


    def select(self, mailbox='INBOX', readonly=False):
        """Select a mailbox.
        Flush all untagged responses.
        (typ, [data]) = <instance>.select(mailbox='INBOX', readonly=False)
        'data' is count of messages in mailbox ('EXISTS' response).
        Mandated responses are ('FLAGS', 'EXISTS', 'RECENT', 'UIDVALIDITY'), so
        other responses should be obtained via <instance>.response('FLAGS') etc.
        """
        


    def setacl(self, mailbox, who, what):
        """Set a mailbox acl.
        (typ, [data]) = <instance>.setacl(mailbox, who, what)
        """
        


    def setannotation(self, *args):
        """(typ, [data]) = <instance>.setannotation(mailbox[, entry, attribute]+)
        Set ANNOTATIONs."""

       


    def setquota(self, root, limits):
        """Set the quota root's resource limits.
        (typ, [data]) = <instance>.setquota(root, limits)
        """
        


    def sort(self, sort_criteria, charset, *search_criteria):
        """IMAP4rev1 extension SORT command.
        (typ, [data]) = <instance>.sort(sort_criteria, charset, search_criteria, ...)
        """
        


    def starttls(self, ssl_context=None):


    def status(self, mailbox, names):
        """Request named status conditions for mailbox.
        (typ, [data]) = <instance>.status(mailbox, names)
        """
        


    def store(self, message_set, command, flags):
        """Alters flag dispositions for messages in mailbox.
        (typ, [data]) = <instance>.store(message_set, command, flags)
        """
        


    def subscribe(self, mailbox):


    def thread(self, threading_algorithm, charset, *search_criteria):


    def uid(self, command, *args):

    def unsubscribe(self, mailbox):


    def unselect(self):


    def xatom(self, name, *args):


    

if HAVE_SSL:

    class IMAP4_SSL(IMAP4):

        """IMAP4 client class over SSL connection
        Instantiate with: IMAP4_SSL([host[, port[, keyfile[, certfile[, ssl_context[, timeout=None]]]]]])
                host - host's name (default: localhost);
                port - port number (default: standard IMAP4 SSL port);
                keyfile - PEM formatted file that contains your private key (default: None);
                certfile - PEM formatted certificate chain file (default: None);
                ssl_context - a SSLContext object that contains your certificate chain
                              and private key (default: None)
                Note: if ssl_context is provided, then parameters keyfile or
                certfile should not be set otherwise ValueError is raised.
                timeout - socket timeout (default: None) If timeout is not given or is None,
                          the global default socket timeout is used
        for more documentation see the docstring of the parent class IMAP4.
        """


        def __init__(self, host='', port=IMAP4_SSL_PORT, keyfile=None,
                     certfile=None, ssl_context=None, timeout=None):
            
        def _create_socket(self, timeout):
            

        def open(self, host='', port=IMAP4_SSL_PORT, timeout=None):

    __all__.append("IMAP4_SSL")

