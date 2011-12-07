#!/usr/bin/env python
# (c) 2011 Anton Romanov
#
#
"""
"""

import os, imp, sys,threading
import re
import socket, asyncore, asynchat
from hon import masterserver,packets
from struct import unpack

home = os.getcwd() 


class Bot( asynchat.async_chat ):
    def __init__( self,config ):
        asynchat.async_chat.__init__( self )   
        self.config = config
        self.nick = 'nickname'
        self.buffer = ''
        self.doc = {}
        self.stats = {}
        self.setup()
        self.id2nick = {}
        

    def write_packet(self,packet_id,*args):
        self.write(packets.packet_factory.pack(packet_id,*args))
 
    def write( self, data ):
        self.push(data)
 
    #def handle_close( self ):
        #print 'disconnected'

    def handle_connect( self ):
        print ('socket connected')
        self.set_terminator(2)
        self.got_len = False
        #self.write(packets.packet_factory.pack(packets.ID.HON_CS_AUTH_INFO,self.account_id,
            #self.cookie,self.ip,self.auth_hash,packets.ID.HON_PROTOCOL_VERSION,5,0))
        self.write_packet(packets.ID.HON_CS_AUTH_INFO,self.account_id,
            self.cookie,self.ip,self.auth_hash,packets.ID.HON_PROTOCOL_VERSION,5,0)

    def collect_incoming_data( self, data ):
        self.buffer += data
 
    def found_terminator( self ):
        if self.got_len:
            self.dispatch(self.buffer)
            self.set_terminator(2)
        else:
            self.set_terminator(unpack(">H",self.buffer)[0])
        self.buffer = ''
        self.got_len = not self.got_len

    def run(self):
        auth_data = masterserver.auth(self.config.nick,self.config.password)
        print ('got auth data')
        #print auth_data,self.config.nick,self.config.password
        self.create_socket( socket.AF_INET, socket.SOCK_STREAM )
        self.ip = auth_data['ip']
        self.cookie = auth_data['cookie']
        self.account_id = int(auth_data['account_id'])
        self.auth_hash = auth_data['auth_hash']
        self.got_len = False
        self.nick = auth_data['nickname']
        self.connect( ( auth_data['chat_url'], packets.ID.HON_CHAT_PORT ) )
        asyncore.loop()
    def setup(self): 
        self.variables = {}

        filenames = []
        if not hasattr(self.config, 'enable'): 
            for fn in os.listdir(os.path.join(home, 'modules')): 
                if fn.endswith('.py') and not fn.startswith('_'): 
                    filenames.append(os.path.join(home, 'modules', fn))
        else: 
            for fn in self.config.enable: 
                filenames.append(os.path.join(home, 'modules', fn + '.py'))

        if hasattr(self.config, 'extra'): 
            for fn in self.config.extra: 
                if os.path.isfile(fn): 
                    filenames.append(fn)
                elif os.path.isdir(fn): 
                    for n in os.listdir(fn): 
                        if n.endswith('.py') and not n.startswith('_'): 
                            filenames.append(os.path.join(fn, n))

        modules = []
        excluded_modules = getattr(self.config, 'exclude', [])
        for filename in filenames: 
            name = os.path.basename(filename)[:-3]
            if name in excluded_modules: continue
            # if name in sys.modules: 
            #     del sys.modules[name]
            try: module = imp.load_source(name, filename)
            except Exception, e: 
                print >> sys.stderr, "Error loading %s: %s (in bot.py)" % (name, e)
            else: 
                if hasattr(module, 'setup'): 
                    module.setup(self)
                self.register(vars(module))
                modules.append(name)

        if modules: 
            print >> sys.stderr, 'Registered modules:', ', '.join(modules)
        else: print >> sys.stderr, "Warning: Couldn't find any modules"

        self.bind_commands()
    def error(self, origin): 
        try: 
            import traceback
            trace = traceback.format_exc()
            print trace
            lines = list(reversed(trace.splitlines()))

            report = [lines[0].strip()]
            for line in lines: 
                line = line.strip()
                if line.startswith('File "/'): 
                    report.append(line[0].lower() + line[1:])
                    break
            else: report.append('source unknown')

            #self.msg(origin.sender, report[0] + ' (' + report[1] + ')')
            print(origin.sender, report[0] + ' (' + report[1] + ')')
        #except: self.msg(origin.sender, "Got an error.")
        except: print(origin.sender, "Got an error.")

    def register(self, variables): 
        # This is used by reload.py, hence it being methodised
        for name, obj in variables.iteritems(): 
            if hasattr(obj, 'commands') or hasattr(obj, 'rule') or hasattr(obj,'event'): 
                self.variables[name] = obj

    def bind_commands(self): 
        self.commands = {'high': {}, 'medium': {}, 'low': {}}
        def bind(self, priority, regexp, func): 
            #print priority, regexp.pattern.encode('utf-8'), func
            # register documentation
            if not hasattr(func, 'name'): 
                func.name = func.__name__
            if func.__doc__: 
                if hasattr(func, 'example'): 
                    example = func.example
                    example = example.replace('$nickname', self.nick)
                else: example = None
                self.doc[func.name] = (func.__doc__, example)
            self.commands[priority].setdefault(regexp, []).append(func)

        def sub(pattern, self=self): 
            # These replacements have significant order
            pattern = pattern.replace('$nickname', re.escape(self.nick))
            return pattern.replace('$nick', r'%s[,:] +' % re.escape(self.nick))

        for name, func in self.variables.iteritems(): 
            #print name, func
            if not hasattr(func, 'priority'): 
                func.priority = 'medium'

            if not hasattr(func, 'thread'): 
                func.thread = True

            if not hasattr(func, 'event'): 
                func.event = [packets.ID.HON_SC_WHISPER,packets.ID.HON_SC_PM,packets.ID.HON_SC_CHANNEL_MSG]

            if hasattr(func, 'rule'): 
                if isinstance(func.rule, str): 
                    pattern = sub(func.rule)
                    regexp = re.compile(pattern)
                    bind(self, func.priority, regexp, func)

                if isinstance(func.rule, tuple): 
                    # 1) e.g. ('$nick', '(.*)')
                    if len(func.rule) == 2 and isinstance(func.rule[0], str): 
                        prefix, pattern = func.rule
                        prefix = sub(prefix)
                        regexp = re.compile(prefix + pattern)
                        bind(self, func.priority, regexp, func)

                    # 2) e.g. (['p', 'q'], '(.*)')
                    elif len(func.rule) == 2 and isinstance(func.rule[0], list): 
                        prefix = self.config.prefix
                        commands, pattern = func.rule
                        for command in commands: 
                            command = r'(%s)\b(?: +(?:%s))?' % (command, pattern)
                            regexp = re.compile(prefix + command)
                            bind(self, func.priority, regexp, func)

                    # 3) e.g. ('$nick', ['p', 'q'], '(.*)')
                    elif len(func.rule) == 3: 
                        prefix, commands, pattern = func.rule
                        prefix = sub(prefix)
                        for command in commands: 
                            command = r'(%s) +' % command
                            regexp = re.compile(prefix + command + pattern)
                            bind(self, func.priority, regexp, func)

            if hasattr(func, 'commands'): 
                for command in func.commands: 
                    template = r'^%s(%s)(?: +(.*))?$'
                    pattern = template % (self.config.prefix, command)
                    regexp = re.compile(pattern)
                    bind(self, func.priority, regexp, func)    

            if not hasattr(func,'commands') and not hasattr(func,'rule'):
                bind(self,func.priority,None,func)

    def wrapped(self, origin, data, match): 
        class PhennyWrapper(object): 
            def __init__(self, phenny): 
                self.bot = phenny

            def __getattr__(self, attr): 
                #sender = origin.sender or text
                #if attr == 'reply': 
                    #return (lambda msg: 
                        #self.bot.msg(sender, origin.nick + ': ' + msg))
                #elif attr == 'say': 
                    #return lambda msg: self.bot.msg(sender, msg)
                if attr == 'reply':
                    if origin[0] == packets.ID.HON_SC_CHANNEL_MSG:
                        return (lambda msg:
                                self.bot.write_packet(origin[0],self.id2nick[origin[1]] + ': ' + msg,
                                    origin[2]))
                    else:
                        return (lambda msg:
                                self.bot.write_packet(origin[0],origin[1],msg))
                elif attr == 'say':
                    if origin[0] == packets.ID.HON_SC_CHANNEL_MSG:
                        return (lambda msg:
                                self.bot.write_packet(origin[0],msg,origin[2]))
                    else:
                        return (lambda msg:
                                self.bot.write_packet(origin[0],origin[1],msg))

                return getattr(self.bot, attr)

        return PhennyWrapper(self)

    def call(self, func, origin, phenny, input): 
        try: func(phenny, input)
        except Exception, e: 
            self.error(origin)

    def input(self, origin, text, data, match): 
        class CommandInput(unicode): 
            def __new__(cls, text, origin, data, match): 
                s = unicode.__new__(cls, text)
                s.origin = origin
                #s.sender = origin.sender
                #s.nick = origin.nick
                s.data = data
                s.match = match
                s.group = match.group
                s.groups = match.groups
                s.admin = origin[1] in self.config.admins
                s.owner = origin[1] == self.config.owner
                return s
        return CommandInput(text, origin, data, match)

    def dispatch(self,data):
        origin,data = packets.packet_factory.parse_packet(data)
        packet_id = origin[0]
        #print 'trying to dispatch',hex(packet_id)

        for priority in ('high', 'medium', 'low'): 
            items = self.commands[priority].items()
            for regexp, funcs in items: 
                for func in funcs: 
                    if packet_id not in func.event: continue
                    if regexp is None:
                        func(self,packet_id,data)
                    elif isinstance(data,unicode):
                        text = data
                        #print (origin, text)
                        #print (regexp.pattern)
                        match = regexp.match(text)
                        if match: 
                            #not sure what that limit is about
                            #if self.limit(origin, func): continue

                            phenny = self.wrapped(origin, text, match)
                            input = self.input(origin, text, data, match)

                            if func.thread: 
                                targs = (func, origin, phenny, input)
                                t = threading.Thread(target=self.call, args=targs)
                                t.start()
                            else: self.call(func, origin, phenny, input)

                            #for source in [origin.sender, origin.nick]: 
                                #try: self.stats[(func.name, source)] += 1
                                #except KeyError: 
                                    #self.stats[(func.name, source)] = 1





