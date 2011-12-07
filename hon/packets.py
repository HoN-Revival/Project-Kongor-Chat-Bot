import struct

class ID:
    #generic constants
    HON_CHAT_PORT = 11031
    HON_PROTOCOL_VERSION = 20
    

    #- Client -> Server
    HON_CS_PONG = 0x2A01
    HON_CS_CHANNEL_MSG = 0x03
    HON_CS_WHISPER = 0x08
    HON_CS_AUTH_INFO = 0x0C00
    HON_CS_BUDDY_ADD_NOTIFY = 0x0D
    HON_CS_JOIN_GAME = 0x10
    HON_CS_CLAN_MESSAGE = 0x13
    HON_CS_PM = 0x1C
    HON_CS_JOIN_CHANNEL = 0x1E
    HON_CS_WHISPER_BUDDIES = 0x20
    HON_CS_LEAVE_CHANNEL = 0x22
    HON_CS_USER_INFO = 0x2A
    HON_CS_UPDATE_TOPIC = 0x30
    HON_CS_CHANNEL_KICK = 0x31
    HON_CS_CHANNEL_BAN = 0x33
    HON_CS_CHANNEL_UNBAN = 0x32
    HON_CS_CHANNEL_SILENCE_USER = 0x38
    HON_CS_CHANNEL_PROMOTE = 0x3A
    HON_CS_CHANNEL_DEMOTE = 0x3B
    HON_CS_CHANNEL_AUTH_ENABLE = 0x3E
    HON_CS_CHANNEL_AUTH_DISABLE = 0x3F
    HON_CS_CHANNEL_AUTH_ADD = 0x40
    HON_CS_CHANNEL_AUTH_DELETE = 0x41
    HON_CS_CHANNEL_AUTH_LIST = 0x42
    HON_CS_CHANNEL_SET_PASSWORD = 0x43
    HON_CS_JOIN_CHANNEL_PASSWORD = 0x46
    HON_CS_CLAN_ADD_MEMBER = 0x47
    HON_CS_CHANNEL_EMOTE = 0x65
    HON_CS_BUDDY_ACCEPT = 0xB3

    #- Server -> Client
    HON_SC_AUTH_ACCEPTED = 0x1c00
    HON_SC_PING = 0x2A00
    HON_SC_CHANNEL_MSG = 0x03
    HON_SC_CHANGED_CHANNEL = 0x04
    HON_SC_JOINED_CHANNEL = 0x05
    HON_SC_LEFT_CHANNEL = 0x06
    HON_SC_WHISPER = 0x08
    HON_SC_WHISPER_FAILED = 0x09
    HON_SC_INITIAL_STATUS = 0x0B
    HON_SC_UPDATE_STATUS = 0xC
    HON_SC_CLAN_MESSAGE = 0x13
    HON_SC_LOOKING_FOR_CLAN = 0x18
    HON_SC_PM = 0x1C
    HON_SC_PM_FAILED = 0x1D
    HON_SC_WHISPER_BUDDIES = 0x20
    HON_SC_MAX_CHANNELS = 0x21
    HON_SC_USER_INFO_NO_EXIST = 0x2B
    HON_SC_USER_INFO_OFFLINE = 0x2C
    HON_SC_USER_INFO_ONLINE = 0x2D
    HON_SC_USER_INFO_IN_GAME = 0x2E
    HON_SC_CHANNEL_UPDATE = 0x2F
    HON_SC_UPDATE_TOPIC = 0x30
    HON_SC_CHANNEL_KICK = 0x31
    HON_SC_CHANNEL_BAN = 0x32
    HON_SC_CHANNEL_UNBAN = 0x33
    HON_SC_CHANNEL_BANNED = 0x34
    HON_SC_CHANNEL_SILENCED = 0x35
    HON_SC_CHANNEL_SILENCE_LIFTED = 0x36
    HON_SC_CHANNEL_SILENCE_PLACED = 0x37
    HON_SC_MESSAGE_ALL = 0x39
    HON_SC_CHANNEL_PROMOTE = 0x3A
    HON_SC_CHANNEL_DEMOTE = 0x3B
    HON_SC_CHANNEL_AUTH_ENABLE = 0x3E
    HON_SC_CHANNEL_AUTH_DISABLE = 0x3F
    HON_SC_CHANNEL_AUTH_ADD  =  0x40
    HON_SC_CHANNEL_AUTH_DELETE = 0x41 
    HON_SC_CHANNEL_AUTH_LIST = 0x42
    HON_SC_CHANNEL_PASSWORD_CHANGED = 0x43
    HON_SC_CHANNEL_ADD_AUTH_FAIL = 0x44
    HON_SC_CHANNEL_DEL_AUTH_FAIL = 0x45
    HON_SC_JOIN_CHANNEL_PASSWORD = 0x46
    HON_SC_CHANNEL_EMOTE = 0x65
    HON_SC_TOTAL_ONLINE = 0x68
    HON_SC_REQUEST_NOTIFICATION = 0xB2
    HON_SC_NOTIFICATION = 0xB4


FILTER=''.join([(len(repr(chr(x)))==3) and chr(x) or '.' for x in range(256)])

def dump(src, length=8):
    N=0; result=''
    while src:
       s,src = src[:length],src[length:]
       hexa = ' '.join(["%02X"%ord(x) for x in s])
       s = s.translate(FILTER)
       result += "%04X   %-*s   %s\n" % (N, length*3, hexa, s)
       N+=length
    return result

class packet_factory:
    chat_packets = [ID.HON_SC_PM,ID.HON_SC_WHISPER,ID.HON_SC_CHANNEL_MSG]
    cs_structs = {
            ID.HON_CS_AUTH_INFO : 'IsssIIB',
            ID.HON_CS_PONG      : '',
            ID.HON_CS_JOIN_CHANNEL : 's',
            ID.HON_CS_PM : 'ss',
            ID.HON_CS_WHISPER : 'ss',
            ID.HON_CS_CHANNEL_MSG : 'sI',
            }
    sc_structs = {
            ID.HON_SC_PING : '',
            ID.HON_SC_PM    : 'ss',
            ID.HON_SC_WHISPER : 'ss',
            ID.HON_SC_CHANNEL_MSG : 'IIs'
            }
    @staticmethod
    def pack(packet_id, *args):
        args = list(args)
        fmt = list(packet_factory.cs_structs[packet_id])
        for i,f in enumerate(fmt):
            if f == 's':
                #print (args[i].__class__.__name__)
                if isinstance(args[i],unicode):
                    args[i] = args[i].encode('utf-8')
                fmt[i] = '{0}s'.format(1 + len(args[i]))
        fmt = ''.join(fmt)
        return struct.pack('<H' + fmt,packet_id,*args)

    @staticmethod
    def parse_packet(data):
        packet_id = struct.unpack('<H',data[:2])[0]
        data = data[2:]
        origin = [packet_id,None,None]
        if packet_id in packet_factory.sc_structs:
            fmt = list(packet_factory.sc_structs[packet_id])
            res = []
            for f in fmt:
                if f == 's':
                    i = data.index('\0')
                    res.append(data[:i].decode("utf-8"))
                    #print res
                    data = data[i+1:]
                else:
                    f = '<' + f
                    i = struct.calcsize(f)
                    res.append(struct.unpack(f,data[:i])[0])
                    data = data[i:]
            data = res

            if packet_id in packet_factory.chat_packets:
                origin[1] = data[0]
                if packet_id == ID.HON_SC_CHANNEL_MSG:
                    origin[2] = data[1]
                    data = data[2]
                else:
                    data = data[1]
            #print(origin,data,isinstance(data,unicode))
        return origin,data