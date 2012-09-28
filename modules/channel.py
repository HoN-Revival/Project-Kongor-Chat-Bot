# -*- coding: utf8 -*-
from hon.packets import ID
from time import sleep
from datetime import datetime
from hon.honutils import normalize_nick

def setup(bot):
    bot.channel_channels = {}
    bot.not_smurfs = []
    bot.config.module_config('channel_limit',[0,'Will try to keep channel at this limit kicking afk non-clanmates'])
    bot.config.module_config('silence_smurfs',[-1,'Will silence anyone with normal mode tmm wins equal or lower than this'])
    bot.config.module_config('spam_threshold',[0,'number of seconds, if user repeats his message in channel with delay lower than this he will be considered spamming and banned'])
    bot.config.module_config('whitelist',[[],'whitelist for antispam etc'])
    bot.config.module_config('default_topic', [{}, 'Set the channel default topic'])

silenced = {}

def silence_smurfs(bot,chanid,nick):
    if bot.config.silence_smurfs < 0:
        return
    if (nick,chanid) in silenced:
        return
    if nick in bot.nick2id and bot.nick2id[nick] in bot.clan_roster:
        return
    if nick in bot.not_smurfs or nick in bot.config.whitelist:
        return
    query = {'nickname' : nick,'f': 'show_stats','table': 'ranked'}
    stats_data = bot.masterserver_request(query,cookie=True)
    if 'rnk_wins' not in stats_data:
        return
    if int(stats_data['rnk_wins']) <= bot.config.silence_smurfs:
        bot.write_packet(ID.HON_CS_CHANNEL_SILENCE_USER,chanid,nick,0x7fffffff)
        silenced[(nick,chanid)] = True
    else:
        bot.not_smurfs.append(nick)

    

def channel_joined_channel(bot,origin,data):
    bot.channel_channels[data[1]] = dict([[m[1],[m[1],m[0],datetime.now(),None]] for m in data[-1]])

    # Default topic setting
    topic = data[3]
    if ( len(topic) == 0 ) or ( topic == "Welcome to the {0} clan channel!".format( bot.clan_info['name'] ) ):
        topics = bot.db.Config("default_topic")
        if topics is not None and bot.id2chan[data[1]] in topics:
            cname = bot.id2chan[data[1]]
            bot.write_packet( ID.HON_CS_UPDATE_TOPIC, data[1], bot.db.Config("default_topic")[cname] )

    #banlist management
    """
    for m in data[-1]:
        nick = normalize_nick(m[0]).lower()
        if bot.store.banlist_re.match(nick):
            bot.write_packet(ID.HON_CS_CHANNEL_BAN,data[1],nick)
        #else:
            #silence_smurfs(bot,data[1],nick)
    """

channel_joined_channel.event = [ID.HON_SC_CHANGED_CHANNEL]

def channel_user_joined_channel_smurfs(bot,origin,data):
    nick = normalize_nick(data[0]).lower()
    silence_smurfs(bot,data[2],nick)
channel_user_joined_channel_smurfs.event = [ID.HON_SC_JOINED_CHANNEL]
channel_user_joined_channel_smurfs.thread = True

def channel_user_joined_channel(bot,origin,data):
    if data[2] not in bot.channel_channels:
        bot.channel_channels[data[2]] = {}
    bot.channel_channels[data[2]][data[1]] = [data[1],data[0],datetime.now(),None]
    l = len(bot.channel_channels[data[2]])
    CHANNEL_MAX = bot.config.channel_limit
    #banlist management
    nick = normalize_nick(data[0]).lower()
    """
    if bot.store.banlist_re.match(nick):
        print("Banlist match: " + nick)
        bot.write_packet(ID.HON_CS_CHANNEL_BAN,data[2],data[0])
    else:
    """
    if CHANNEL_MAX == 0:
        return
    if l > CHANNEL_MAX:
        l -= CHANNEL_MAX
        for i in sorted(bot.channel_channels[data[2]].values(), key=lambda x:x[2]):
            if l <= 0:break
            nick = normalize_nick(i[1])
            if i[0] not in bot.clan_roster and nick not in bot.config.whitelist and i[1].split(']')[0] not in ['[GM','[S2']:
                bot.write_packet(ID.HON_CS_CHANNEL_KICK,data[2],i[0])
                sleep(0.5)
                bot.write_packet(ID.HON_CS_WHISPER,i[1],'Sorry, too many people in channel, we need some place for active members')
                l -= 1
                sleep(0.5)
channel_user_joined_channel.event = [ID.HON_SC_JOINED_CHANNEL]
channel_user_joined_channel.thread = False

def channel_user_left_channel(bot,origin,data):
    try:
        del(bot.channel_channels[data[1]][data[0]])
    except:
        pass
channel_user_left_channel.event = [ID.HON_SC_LEFT_CHANNEL]

def update_stats(bot,origin,data):
    time = datetime.now()
    if (time - bot.channel_channels[origin[2]][origin[1]][2]).seconds < bot.config.spam_threshold and data == bot.channel_channels[origin[2]][origin[1]][3]:
        nick = bot.id2nick[origin[1]].lower()
        bot.write_packet(ID.HON_CS_CHANNEL_BAN,origin[2],nick)
        # bot.config.set_add('banlist',nick)
        bot.banlist.Add(nick)
    bot.channel_channels[origin[2]][origin[1]][2] = time
    bot.channel_channels[origin[2]][origin[1]][3] = data
update_stats.event = [ID.HON_SC_CHANNEL_MSG]

def kickall(bot,input):
    if not input.admin:
        return False
    if input.origin[2] in bot.channel_channels:
        for i in bot.channel_channels[input.origin[2]]:
            if i[0] not in bot.clan_roster and i[1].split(']')[0] not in ['[GM','[S2','[TECH']:
                bot.write_packet(ID.HON_CS_CHANNEL_KICK,input.origin[2],i[0])
                sleep(0.5)
kickall.commands = ['kickall']
kickall.event = [ID.HON_SC_CHANNEL_MSG]
kickall.thread = False

def unwhitelist(bot,input):
    if not input.admin:
        return False
    bot.config.set_del('whitelist',input.group(2).lower())
unwhitelist.commands = ['unwhitelist']
def whitelist(bot,input):
    if not input.admin:
        return False
    bot.config.set_add('whitelist',input.group(2).lower())
whitelist.commands = ['whitelist']

def kick(bot, input): 
    """makes bot kick user""" 
    if not input.admin: return False
    if not input.group(2): return
    if not input.group(3) and input.origin[0] == ID.HON_SC_CHANNEL_MSG:
        bot.write_packet(ID.HON_CS_CHANNEL_KICK,input.origin[2],bot.nick2id[input.group(2).lower()])
    else:
        nick = input.group(2)
        chan = input.group(3)
        if chan is not None:
            chan = bot.chan2id[chan.lower()]
        elif input.origin[0] == ID.HON_SC_CHANNEL_MSG:
            chan = input.origin[2]
        if chan is not None:
            bot.write_packet(ID.HON_CS_CHANNEL_KICK,chan,bot.nick2id[nick.lower()])
kick.rule = (['kick'],'([^\ ]+)(?:\ +(.+))?')

def promote(bot, input): 
    """makes bot promote user""" 
    if not input.admin: return False
    if not input.group(2) and input.origin[0] == ID.HON_SC_CHANNEL_MSG:
        bot.write_packet(ID.HON_CS_CHANNEL_PROMOTE,input.origin[2],input.account_id)
    else:
        nick = input.group(2)
        chan = input.group(3)
        if chan is not None:
            chan = bot.chan2id[chan.lower()]
        elif input.origin[0] == ID.HON_SC_CHANNEL_MSG:
            chan = input.origin[2]
        if chan is not None:
            bot.write_packet(ID.HON_CS_CHANNEL_PROMOTE,chan,bot.nick2id[nick.lower()])
promote.rule = (['promote'],'([^\ ]+)?(?:\ +(.+))?')

def demote(bot, input): 
    """makes bot demote user""" 
    if not input.admin: return False
    if not input.group(2) and input.origin[0] == ID.HON_SC_CHANNEL_MSG:
        bot.write_packet(ID.HON_CS_CHANNEL_DEMOTE,input.origin[2],input.account_id)
    else:
        nick = input.group(2)
        chan = input.group(3)
        if chan is not None:
            chan = bot.chan2id[chan.lower()]
        elif input.origin[0] == ID.HON_SC_CHANNEL_MSG:
            chan = input.origin[2]
        if chan is not None:
            bot.write_packet(ID.HON_CS_CHANNEL_DEMOTE,chan,bot.nick2id[nick.lower()])
demote.rule = (['demote'],'([^\ ]+)?(?:\ +(.+))?')

def dtopic(bot, input):
    """Set default channel topic, run this from intended channel"""
    if not input.admin:
        return False
    if not input.origin[0] == ID.HON_SC_CHANNEL_MSG:
        bot.reply("Run me from channel intended for the default topic!")
    else:
        cname = bot.id2chan[input.origin[2]]
        if input.group(2):
            print( "Inserting dtopic for {0}: {1}".format( cname, input.group(2) ) )
            bot.db.Config("default_topic", {cname: input.group(2)})
        else:
            topics = bot.db.Config("default_topic")
            if topics is not None and cname in topics:
                bot.reply( "Current: {0}".format( bot.config.default_topic[cname] ) )
            else:
                bot.reply( "Default topic for the current channel is not set." )
dtopic.commands = ['dtopic']

def topic(bot,input):
    """Sets topic on channel issued"""
    if not input.admin:
        return False
    bot.write_packet(ID.HON_CS_UPDATE_TOPIC,input.origin[2],input.group(2))
topic.commands = ['topic']
topic.event = [ID.HON_SC_CHANNEL_MSG]

def silence(bot, input): 
    """makes bot silence user, seconds""" 
    if not input.admin: return False
    nick = input.group(2)
    time = input.group(3)
    chan = input.group(4)
    if chan is not None:
        chan = bot.chan2id[chan.lower()]
    elif input.origin[0] == ID.HON_SC_CHANNEL_MSG:
        chan = input.origin[2]
    if chan is not None and time is not None and nick is not None:
        bot.write_packet(ID.HON_CS_CHANNEL_SILENCE_USER,chan,nick,1000*int(time))
silence.rule = (['silence'],'([^\ ]+) ([0-9]+)(?:\ +(.+))?')