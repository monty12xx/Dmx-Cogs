import discord
from discord.ext import commands
from .utils.chat_formatting import *
import random
from random import randint
from random import choice as randchoice
import datetime
from __main__ import send_cmd_help
import re
import urllib
import time
import aiohttp
from .utils import checks
import asyncio
from cogs.utils.dataIO import dataIO
import io, os
from .utils.dataIO import fileIO
import logging


settings = {"POLL_DURATION" : 60}

JSON = 'data/away/away.json'

class General:
    """General commands."""

    def __init__(self, bot):
        self.bot = bot
        self.data = dataIO.load_json(JSON)
        self.stopwatches = {}
        self.reminders = fileIO("data/remind/reminders.json", "load")
        self.units = {"minute" : 60, "hour" : 3600, "day" : 86400, "week": 604800, "month": 2592000}
        self.settings = 'data/youtube/settings.json'
        self.youtube_regex = (
          r'(https?://)?(www\.)?'
          '(youtube|youtu|youtube-nocookie)\.(com|be)/'
          '(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})')

        self.settings_file = 'data/weather/weather.json'
        self.ball = ["As I see it, yes", "It is certain", "It is decidedly so", "Most likely", "Outlook good",
                     "Signs point to yes", "Without a doubt", "Yes", "Yes – definitely", "You may rely on it", "Reply hazy, try again",
                     "Ask again later", "Better not tell you now", "Cannot predict now", "Concentrate and ask again",
                     "Don't count on it", "My reply is no", "My sources say no", "Outlook not so good", "Very doubtful"]
        self.poll_sessions = []

    async def listener(self, message):
        if not message.channel.is_private and self.bot.user.id != message.author.id:
            server = message.server
            channel = message.channel
            author = message.author
            ts = message.timestamp
            filename = 'data/seen/{}/{}.json'.format(server.id, author.id)
            if not os.path.exists('data/seen/{}'.format(server.id)):
                os.makedirs('data/seen/{}'.format(server.id))
            data = {}
            data['TIMESTAMP'] = '{} {}:{}:{}'.format(ts.date(), ts.hour, ts.minute, ts.second)
            data['MESSAGE'] = message.clean_content
            data['CHANNEL'] = channel.mention
            dataIO.save_json(filename, data)

    async def _get_local_time(self, lat, lng):
        settings = dataIO.load_json(self.settings_file)
        if 'TIME_API_KEY' in settings:
            api_key = settings['TIME_API_KEY']
            if api_key != '':
                payload = {'format': 'json', 'key': api_key, 'by': 'position', 'lat': lat, 'lng': lng}
                url = 'http://api.timezonedb.com/v2/get-time-zone?'
                headers = {'user-agent': 'Red-cog/1.0'}
                conn = aiohttp.TCPConnector(verify_ssl=False)
                session = aiohttp.ClientSession(connector=conn)
                async with session.get(url, params=payload, headers=headers) as r:
                    parse = await r.json()
                session.close()
                if parse['status'] == 'OK':
                    return datetime.datetime.fromtimestamp(int(parse['timestamp'])-7200).strftime('%Y-%m-%d %H:%M')
        return

    async def listener(self, message):
        if not message.channel.is_private:
            if message.author.id != self.bot.user.id:
                server_id = message.server.id
                data = dataIO.load_json(self.settings)
                if server_id not in data:
                    enable_delete = False
                    enable_meta = False
                    enable_url = False
                else:
                    enable_delete = data[server_id]['ENABLE_DELETE']
                    enable_meta = data[server_id]['ENABLE_META']
                    enable_url = data[server_id]['ENABLE_URL']
                if enable_meta:
                    url = re.findall('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', message.content)
                    if url:
                        is_youtube_link = re.match(self.youtube_regex, url[0])
                        if is_youtube_link:
                            yt_url = "http://www.youtube.com/oembed?url={0}&format=json".format(url[0])
                            metadata = await self.get_json(yt_url)
                            if enable_url:
                                msg = '**Title:** _{}_\n**Uploader:** _{}_\n_YouTube url by {}_\n\n{}'.format(metadata['title'], metadata['author_name'], message.author.name, url[0])
                                if enable_delete:
                                    try:
                                        await self.bot.delete_message(message)
                                    except:
                                        pass
                            else:
                                if enable_url:
                                    x = '\n_YouTube url by {}_'.format(message.author.name)
                                else:
                                    x = ''
                                msg = '**Title:** _{}_\n**Uploader:** _{}_{}'.format(metadata['title'], metadata['author_name'], x)
                            await self.bot.send_message(message.channel, msg)

    async def listener(self, message):
        tmp = {}
        for mention in message.mentions:
            tmp[mention] = True
        if message.author.id != self.bot.user.id:
            for author in tmp:
                if author.id in self.data:
                    avatar = author.avatar_url if author.avatar else author.default_avatar_url
                    if self.data[author.id]['MESSAGE']:
                        em = discord.Embed(description=self.data[author.id]['MESSAGE'], color=discord.Color.orange())
                        em.set_author(name='{} s currently away And Says ↓⇓⟱'.format(author.display_name), icon_url=avatar)
                    else:
                        em = discord.Embed(color=discord.Color.purple())
                        em.set_author(name='{} is currently away'.format(author.display_name), icon_url=avatar)
                    await self.bot.send_message(message.channel, embed=em)

    async def check_reminders(self):
        while self is self.bot.get_cog("general"):
            to_remove = []
            for reminder in self.reminders:
                if reminder["FUTURE"] <= int(time.time()):
                    try:
                        await self.bot.send_message(discord.User(id=reminder["ID"]), "**Hey!!** {} You've asked me to remind you this \n{}".format(user.name, reminder["TEXT"]))
                    except (discord.errors.Forbidden, discord.errors.NotFound):
                        to_remove.append(reminder)
                    except discord.errors.HTTPException:
                        pass
                    else:
                        to_remove.append(reminder)
            for reminder in to_remove:
                self.reminders.remove(reminder)
            if to_remove:
                fileIO("data/remind/reminders.json", "save", self.reminders)
            await asyncio.sleep(5)

    @commands.command(pass_context=True, name="away")
    async def _away(self, context, *message: str):
        """Tell the bot you're away or back."""
        author = context.message.author
        if author.id in self.data:
            del self.data[author.id]
            msg = 'Welcome back :space_invader: :D.'
        else:
            self.data[context.message.author.id] = {}
            if len(str(message)) < 256:
                self.data[context.message.author.id]['MESSAGE'] = ' '.join(context.message.clean_content.split()[1:])
            else:
                self.data[context.message.author.id]['MESSAGE'] = True
            msg = '__You\'re now set as away__ :wave: ,***Get out of here!*** :point_right:  :door: .'
        dataIO.save_json(JSON, self.data)
        await self.bot.say(msg)

    async def get_song_metadata(self, song_url):
        """
        Returns JSON object containing metadata about the song.
        """

        is_youtube_link = re.match(self.youtube_regex, song_url)

        if is_youtube_link:
            url = "http://www.youtube.com/oembed?url={0}&format=json".format(song_url)
            result = await self.get_json(url)
        else:
            result = {"title": "A song "}
        return result

    async def get_json(self, url):
        """
        Returns the JSON from an URL.
        Expects the url to be valid and return a JSON object.
        """
        async with aiohttp.get(url) as r:
            result = await r.json()
        return result

    @commands.command(pass_context=True, name='youtube', no_pm=True)
    async def _youtube(self, context, *, query: str):
        """Search on Youtube"""
        try:
            url = 'https://www.youtube.com/results?'
            payload = {'search_query': " ".join(query), 'hl': 'en'}
            headers = {'user-agent': 'Red-cog/1.0'}
            conn = aiohttp.TCPConnector(verify_ssl=False)
            session = aiohttp.ClientSession(connector=conn)
            async with session.get(url, params=payload, headers=headers) as r:
                result = await r.text()
            session.close()
            yt_find = re.findall(r'href=\"\/watch\?v=(.{11})', result)
            url = 'https://www.youtube.com/watch?v={}'.format(yt_find[0])
            metadata = await self.get_song_metadata(url)
            em = discord.Embed(title=metadata['author_name'], color=discord.Color.red(), url=metadata['author_url'])
            em.set_author(name=metadata['title'], url=url)
            em.set_image(url=metadata['thumbnail_url'])
            # em.video.url = url
            # em.video.width = 480
            # em.video.height = 270
            await self.bot.say(embed=em)
        except Exception as e:
            message = 'Something went terribly wrong! [{}]'.format(e)
            await self.bot.say(message)

    @commands.group(pass_context=True, name='youtubetoggle', aliases=['ytoggle'])
    @checks.mod_or_permissions(administrator=True)
    async def _youtubetoggle(self, context):
        """
        Toggle metadata and preview features
        """
        data = dataIO.load_json(self.settings)
        server_id = context.message.server.id
        if server_id not in data:
            data[server_id] = {}
            data[server_id]['ENABLE_URL'] = False
            data[server_id]['ENABLE_DELETE'] = False
            data[server_id]['ENABLE_META'] = False
            dataIO.save_json(self.settings, data)
        if context.invoked_subcommand is None:
            await send_cmd_help(context)

    @_youtubetoggle.command(pass_context=True, name='url')
    async def _url(self, context):
        """
        Toggle showing url
        """
        data = dataIO.load_json(self.settings)
        server_id = context.message.server.id
        if data[server_id]['ENABLE_URL'] is False:
            data[server_id]['ENABLE_URL'] = True
            message = 'URL now enabled'
        elif data[server_id]['ENABLE_URL'] is True:
            data[server_id]['ENABLE_URL'] = False
            message = 'URL now disabled'
        else:
            pass
        dataIO.save_json(self.settings, data)
        await self.bot.say(message)

    @_youtubetoggle.command(pass_context=True, name='meta')
    async def _meta(self, context):
        """
        Toggle showing metadata
        """
        data = dataIO.load_json(self.settings)
        server_id = context.message.server.id
        if data[server_id]['ENABLE_META'] is False:
            data[server_id]['ENABLE_META'] = True
            message = 'Metadata now enabled'
        elif data[server_id]['ENABLE_META'] is True:
            data[server_id]['ENABLE_META'] = False
            message = 'Metadata now disabled'
        else:
            pass
        dataIO.save_json(self.settings, data)
        await self.bot.say('`{}`'.format(message))

    @_youtubetoggle.command(pass_context=True, name='delete')
    async def _delete(self, context):
        """
        Toggle deleting message
        """
        data = dataIO.load_json(self.settings)
        server_id = context.message.server.id
        if data[server_id]['ENABLE_DELETE'] is False:
            data[server_id]['ENABLE_DELETE'] = True
            message = 'Delete now enabled'
        elif data[server_id]['ENABLE_DELETE'] is True:
            data[server_id]['ENABLE_DELETE'] = False
            message = 'Delete now disabled'
        else:
            pass
        dataIO.save_json(self.settings, data)
        await self.bot.say('`{}`'.format(message))

    @commands.command(pass_context=True, name='weather', aliases=['we'])
    async def _weather(self, context, *arguments: str):
        """Get the weather!"""
        settings = dataIO.load_json(self.settings_file)
        api_key = settings['WEATHER_API_KEY']
        if len(arguments) == 0:
            message = 'No location provided.'
        elif api_key != '':
            try:
                payload = {'q': " ".join(arguments), 'appid': api_key}
                url = 'http://api.openweathermap.org/data/2.5/weather?'
                headers = {'user-agent': 'Red-cog/1.0'}
                conn = aiohttp.TCPConnector(verify_ssl=False)
                session = aiohttp.ClientSession(connector=conn)
                async with session.get(url, params=payload, headers=headers) as r:
                    parse = await r.json()
                session.close()
                lat = parse['coord']['lat']
                lng = parse['coord']['lon']
                local_time = await self._get_local_time(lat, lng)
                celcius = round(int(parse['main']['temp'])-273)+1
                fahrenheit = round(int(parse['main']['temp'])*9/5-459)+2
                temperature = '{0} Celsius / {1} Fahrenheit'.format(celcius, fahrenheit)
                humidity = str(parse['main']['humidity']) + '%'
                pressure = str(parse['main']['pressure']) + ' hPa'
                wind_kmh = str(round(parse['wind']['speed'] * 3.6)) + ' km/h'
                wind_mph = str(round(parse['wind']['speed'] * 2.23694)) + ' mph'
                clouds = parse['weather'][0]['description'].title()
                icon = parse['weather'][0]['icon']
                name = parse['name'] + ', ' + parse['sys']['country']
                city_id = parse['id']
                em = discord.Embed(title='Weather in :earth_americas: {} - {}'.format(name, local_time), color=discord.Color.blue(), description='\a\n', url='https://openweathermap.org/city/{}'.format(city_id))
                em.add_field(name=' :cloud: **Conditions**', value=clouds)
                em.add_field(name=':thermometer: **Temperature**', value=temperature)
                em.add_field(name=' :dash: **Wind**', value='{} / {}'.format(wind_kmh, wind_mph))
                em.add_field(name=' :compression: **Pressure**', value=pressure)
                em.add_field(name=' :sweat: **Humidity**', value=humidity)
                em.set_thumbnail(url='https://openweathermap.org/img/w/{}.png'.format(icon))
                em.add_field(name='\a', value='\a')
                em.add_field(name='\a', value='\a')
                em.set_footer(text='Weather data provided by OpenWeatherMap', icon_url='http://openweathermap.org/themes/openweathermap/assets/vendor/owm/img/icons/logo_16x16.png')
                await self.bot.say(embed=em)
            except KeyError:
                message = 'Location not found.'
                await self.bot.say('```{}```'.format(message))
        else:
            message = 'No API key set. Get one at http://openweathermap.org/'
            await self.bot.say('```{}```'.format(message))

    @commands.command(pass_context=True, name='weatherkey')
    @checks.is_owner()
    async def _weatherkey(self, context, key: str):
        """Acquire a key from  http://openweathermap.org/"""
        settings = dataIO.load_json(self.settings_file)
        settings['WEATHER_API_KEY'] = key
        dataIO.save_json(self.settings_file, settings)

    @commands.command(pass_context=True, name='timekey')
    @checks.is_owner()
    async def _timekey(self, context, key: str):
        """Acquire a key from https://timezonedb.com/api"""
        settings = dataIO.load_json(self.settings_file)
        settings['TIME_API_KEY'] = key
        dataIO.save_json(self.settings_file, settings)

    @commands.command()
    async def lenny(self):
        """This does stuff( ͡° ͜ʖ ͡°)!"""

        await self.bot.say("( ͡° ͜ʖ ͡°)")
    @commands.command()
    async def bangers(self):
        """Dangerous's playlist"""

        await self.bot.say(" Heres the playlist enjoy the tunes :musical_note: https://www.youtube.com/playlist?list=PL42LCVbTlLSywDEpoLDWdDdjZDVgNsD5A :musical_note: ")

    @commands.command(pass_context=True, no_pm=True, name='seen')
    async def _seen(self, context, username: discord.Member):
        '''seen <@username>'''
        server = context.message.server
        author = username
        filename = 'data/seen/{}/{}.json'.format(server.id, author.id)
        if dataIO.is_valid_json(filename):
            data = dataIO.load_json(filename)
            ts = data['TIMESTAMP']
            last_message = data['MESSAGE']
            channel = data['CHANNEL']
            em = discord.Embed(description='\a\n{}'.format(last_message), color=discord.Color.green())
            avatar = author.avatar_url if author.avatar else author.default_avatar_url
            em.set_author(name='{} was last seen on {} UTC'.format(author.display_name, ts), icon_url=avatar)
            em.add_field(name='\a', value='**Channel:** {}'.format(channel))
            await self.bot.say(embed=em)
        else:
            message = 'I haven\'t seen {} yet.'.format(author.display_name)
            await self.bot.say('{}'.format(message))

    @commands.command(pass_context=True)
    async def emoji(self, ctx, name: str):
        """Send a large custom emoji. 
        Bot must be in the server with the emoji"""
        for x in list(self.bot.get_all_emojis()):
            if x.name.lower() == name.lower():
                fdir ="data/moji/" + x.server.name
                fp = fdir + "/{0.name}.png".format(x)
                if not os.path.exists(fdir):
                    os.mkdir(fdir)
                if not os.path.isfile(fp):
                    async with aiohttp.get(x.url) as r:
                        img_bytes = await r.read()
                        img = io.BytesIO(img_bytes)
                        with open(fp, 'wb') as o:
                            o.write(img.read())
                        o.close()

#You can uncomment this line if you want c: 
                #await self.bot.delete_message(ctx.message)
                return await self.bot.send_file(ctx.message.channel, fp)

    @commands.group(pass_context=True)
    async def moji(self, ctx):
        """Various emoji operations"""
        if ctx.invoked_subcommand is None:
            return await send_cmd_help(ctx)

    @moji.command(pass_context=True)
    async def list(self, ctx, server: int = None):
        """List all available custom emoji"""
        server = server
        servers = list(self.bot.servers)
        if server is None:
            msg = "``` Available servers:"
            for x in servers:
                msg += "\n\t" + str(servers.index(x)) + ("- {0.name}".format(x))
            await self.bot.say(msg + "```")
        else:
            msg = "```Emojis for {0.name}".format(servers[server])
            for x in list(servers[server].emojis):
                msg += "\n\t" + str(x.name)
            await self.bot.say(msg + "```")

    @commands.command()
    async def penis(self, user : discord.Member):
        """Detects user's penis length

        This is 100% accurate."""
        random.seed(user.id)
        p = "8" + "="*random.randint(0, 50) + "D"
        await self.bot.say("Size: " + p)

    @commands.command(pass_context=True)
    async def quote(self, ctx, message_id = None):
        """Quotes a Message. If not specified, I will pick one for you"""
        if message_id is None:
            async for m in self.bot.logs_from(ctx.message.channel, limit=500):
                msg = m
        else:
            msg = await self.bot.get_message(ctx.message.channel, id = str(message_id))
        colour = ''.join([randchoice('0123456789ABCDEF') for x in range(6)])
        colour = int(colour, 16) 
        owner = msg.author.name+"#"+msg.author.discriminator
        a = discord.Embed()
        a.description = msg.content
        avatar = msg.author.default_avatar_url if not msg.author.avatar else msg.author.avatar_url
        a.set_author(name=owner, icon_url=avatar)
        a.timestamp = msg.timestamp
        a.colour = colour
        await self.bot.send_message(msg.channel, embed = a)

    @commands.command()
    async def choose(self, *choices):
        """Chooses between multiple choices.
        To denote multiple choices, you should use double quotes.
        """
        choices = [escape_mass_mentions(choice) for choice in choices]
        if len(choices) < 2:
            await self.bot.say('Not enough choices to pick from.')
        else:
            await self.bot.say(randchoice(choices))

    @commands.command(pass_context=True)
    async def ping(self,ctx):
        """Get the ping time fam"""
        channel = ctx.message.channel
        user = ctx.message.author
        colour = ''.join([randchoice('0123456789ABCDEF') for x in range(6)])
        colour = int(colour, 16)
        t1 = time.perf_counter()
        await self.bot.send_typing(channel)
        t2 = time.perf_counter()
        if user.nick is None:
            user.nick=user.name
        em = discord.Embed(description="Hey _{}!!_  the bloody ping is ==> _{}ms_ Das a mad ting rite!?!".format(user.nick, round((t2-t1)*1000)), colour=discord.Colour(value=colour))

        await self.bot.say(embed=em)
    @commands.command(pass_context=True)
    async def test(self, message):
        pingtime = time.time()
        pingms = await self.bot.say("pinging server...")
        ping = time.time() - pingtime
        await self.bot.edit_message(pingms, "It took **%.01f** secs" % (ping) + " to ping.")

    @commands.command(pass_context=True)
    async def remind(self, ctx,  quantity : int, time_unit : str, *, text : str):
        """Sends you <text> when the time has elapsed
        Units: minutes, hours, days, weeks, month
        Example:
        [p]remind 3 days Kill myself
        Cog by 26."""
        time_unit = time_unit.lower()
        author = ctx.message.author
        s = ""
        if time_unit.endswith("s"):
            time_unit = time_unit[:-1]
            s = "s"
        if not time_unit in self.units:
            await self.bot.say(":noo_good: Time units are **As Follows**:\n minute, hour, day, week, month")
            return
        if quantity < 1:
            await self.bot.say(":bangbang: Number cannot be negative or lower.:x:")
            return
        if len(text) > 1960:
            await self.bot.say("https://goo.gl/Me042H That text is too long Boi.")
            return
        seconds = self.units[time_unit] * quantity
        future = int(time.time()+seconds)
        self.reminders.append({"ID" : author.id, "FUTURE" : future, "TEXT" : text})
        logger.info("{} ({}) set a reminder.".format(author.name, author.id))
        await self.bot.say(":thumbsup: **Gotcha !!** Ima remind you that in ***{} {}. :smile:***".format(str(quantity), time_unit + s))
        fileIO("data/remind/reminders.json", "save", self.reminders)

    @commands.command(pass_context=True)
    async def forget(self, ctx):
        """Removes all your upcoming notifications"""
        author = ctx.message.author
        to_remove = []
        for reminder in self.reminders:
            if reminder["ID"] == author.id:
                to_remove.append(reminder)

        if not to_remove == []:
            for reminder in to_remove:
                self.reminders.remove(reminder)
            fileIO("data/remind/reminders.json", "save", self.reminders)
            await self.bot.say("**Notifications Removed** :thumbsup:")
        else:
            await self.bot.say(":no_good: You have **No** Notifications :thinking:")

    async def check_reminders(self):
        while self is self.bot.get_cog("general"):
            to_remove = []
            for reminder in self.reminders:
                if reminder["FUTURE"] <= int(time.time()):
                    try:
                        await self.bot.send_message(discord.User(id=reminder["ID"]), "**Hey!!** {} You've asked me to remind you this \n{}".format(user.name, reminder["TEXT"]))
                    except (discord.errors.Forbidden, discord.errors.NotFound):
                        to_remove.append(reminder)
                    except discord.errors.HTTPException:
                        pass
                    else:
                        to_remove.append(reminder)
            for reminder in to_remove:
                self.reminders.remove(reminder)
            if to_remove:
                fileIO("data/remind/reminders.json", "save", self.reminders)
            await asyncio.sleep(5)

    @commands.command(pass_context=True)
    async def roll(self, ctx, number : int = 100):
        """Rolls random number (between 1 and user choice)
        Defaults to 100.
        """
        author = ctx.message.author
        if number > 1:
            n = randint(1, number)
            await self.bot.say("{} :game_die: {} :game_die:".format(author.mention, n))
        else:
            await self.bot.say("{} Maybe higher than 1? ;P".format(author.mention))

    @commands.command(pass_context=True)
    async def flip(self, ctx, user : discord.Member=None):
        """Flips a coin... or a user.
        Defaults to coin.
        """
        if user != None:
            msg = ""
            if user.id == self.bot.user.id:
                user = ctx.message.author
                msg = "Nice try. You think this is funny? How about *this* instead:\n\n"
            char = "abcdefghijklmnopqrstuvwxyz"
            tran = "ɐqɔpǝɟƃɥᴉɾʞlɯuodbɹsʇnʌʍxʎz"
            table = str.maketrans(char, tran)
            name = user.display_name.translate(table)
            char = char.upper()
            tran = "∀qƆpƎℲפHIſʞ˥WNOԀQᴚS┴∩ΛMX⅄Z"
            table = str.maketrans(char, tran)
            name = name.translate(table)
            await self.bot.say(msg + "(╯°□°）╯︵ " + name[::-1])
        else:
            await self.bot.say("*flips a coin and... " + randchoice(["HEADS!*", "TAILS!*"]))

    @commands.command(pass_context=True, name='wikipedia', aliases=['wiki'])
    async def _wikipedia(self, context, *, query: str):
        """
        Get information from Wikipedia
        """
        try:
            url = 'https://en.wikipedia.org/w/api.php?'
            payload = {}
            payload['action'] = 'query'
            payload['format'] = 'json'
            payload['prop'] = 'extracts'
            payload['titles'] = ''.join(query).replace(' ', '_')
            payload['exsentences'] = '5'
            payload['redirects'] = '1'
            payload['explaintext'] = '1'
            headers = {'user-agent': 'Red-cog/1.0'}
            conn = aiohttp.TCPConnector(verify_ssl=False)
            session = aiohttp.ClientSession(connector=conn)
            async with session.get(url, params=payload, headers=headers) as r:
                result = await r.json()
            session.close()
            if '-1' not in result['query']['pages']:
                for page in result['query']['pages']:
                    title = result['query']['pages'][page]['title']
                    description = result['query']['pages'][page]['extract'].replace('\n', '\n\n')
                em = discord.Embed(title='Wikipedia: {}'.format(title), description='\a\n{}...\n\a'.format(description[:-3]), color=discord.Color.blue(), url='https://en.wikipedia.org/wiki/{}'.format(title.replace(' ', '_')))
                em.set_footer(text='Information provided by Wikimedia', icon_url='https://upload.wikimedia.org/wikipedia/commons/thumb/5/53/Wikimedia-logo.png/600px-Wikimedia-logo.png')
                await self.bot.say(embed=em)
            else:
                message = 'I\'m sorry, I can\'t find {}'.format(''.join(query))
                await self.bot.say('```{}```'.format(message))
        except Exception as e:
            message = 'Something went terribly wrong! [{}]'.format(e)
            await self.bot.say('```{}```'.format(message))

    @commands.command(pass_context=True, no_pm=True)
    async def gsinvite(self, ctx):
        """Get a invite to the current server"""

        colour = ''.join([randchoice('0123456789ABCDEF') for x in range(6)])
        colour = int(colour, 16)

        try:
            invite = await self.bot.create_invite(ctx.message.server)
        except:
            await self.bot.say("I do not have the `Create Instant Invite` Permission")
            return

        server = ctx.message.server

        randnum = randint(1, 10)
        empty = u"\u2063"
        emptyrand = empty * randnum

        data = discord.Embed(
            colour=discord.Colour(value=colour))
        data.add_field(name=server.name, value=invite, inline=False)

        if server.icon_url:
            data.set_thumbnail(url=server.icon_url)

        try:
            await self.bot.say(emptyrand, embed=data)
        except:
            await self.bot.say("I need the `Embed links` permission "
                               "to send this")

    @commands.command(pass_context=True, hidden = True, no_pm=True)
    async def pwincess(self, ctx):
        """Command special for pwincess <3"""
        user = ctx.message.author
        if user.id == "105899177401180160" or user.id == "187570149207834624":
            await self.bot.say(":two_hearts: <@105899177401180160> is my master, waifu and goddess. :heart_eyes: :heart:️ :ok_hand: :fire:️")
            return
        else:
            await self.bot.reply(":x: Sorry i only Reply to my master waifu goddess Pwincess :stuck_out_tongue:")

    @commands.command(name = "google", pass_context=True, no_pm=True)
    @commands.cooldown(5, 60, commands.BucketType.user)
    async def _google(self, ctx, text):
        """Its google, you search with it.
        Example: google A french pug
        Special search options are available; Image, Images, Maps
        Example: google image You know, for kids! > Returns first image"""
        search_type = ctx.message.content[len(ctx.prefix+ctx.command.name)+1:].lower().split(" ")
        option = {'User-Agent' : 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.1'}
        regex = [",\"ou\":\"([^`]*?)\"", "<h3 class=\"r\"><a href=\"\/url\?url=([^`]*?)&amp;", "<h3 class=\"r\"><a href=\"([^`]*?)\""]

        #Start of Image
        if search_type[0] == "image":
            search_valid = str(ctx.message.content[len(ctx.prefix+ctx.command.name)+1:].lower())
            if search_valid == "image":
                await self.bot.say("Please actually search something")
            else:
                uri = "https://www.google.com/search?tbm=isch&tbs=isz:m&q="
                quary = str(ctx.message.content[len(ctx.prefix+ctx.command.name)+7:].lower())
                encode = urllib.parse.quote_plus(quary,encoding='utf-8',errors='replace')
                uir = uri+encode

                async with aiohttp.get(uir, headers = option) as resp:
                    test = await resp.content.read()
                    unicoded = test.decode("unicode_escape")
                    query_find = re.findall(regex[0], unicoded)
                    try:
                        url = query_find[0]
                        await self.bot.say(url)
                    except IndexError:
                        await self.bot.say("Your search yielded no results.")
            #End of Image
        #Start of Image random
        elif search_type[0] == "images":
            search_valid = str(ctx.message.content[len(ctx.prefix+ctx.command.name)+1:].lower())
            if search_valid == "image":
                await self.bot.say("Please actually search something")
            else:
                uri = "https://www.google.com/search?tbm=isch&tbs=isz:m&q="
                quary = str(ctx.message.content[len(ctx.prefix+ctx.command.name)+7:].lower())
                encode = urllib.parse.quote_plus(quary,encoding='utf-8',errors='replace')
                uir = uri+encode
                async with aiohttp.get(uir, headers = option) as resp:
                    test = await resp.content.read()
                    unicoded = test.decode("unicode_escape")
                    query_find = re.findall(regex[0], unicoded)
                    try:
                        url = choice(query_find)
                        await self.bot.say(url)
                    except IndexError:
                        await self.bot.say("Your search yielded no results.")
            #End of Image random
        #Start of Maps
        elif search_type[0] == "maps":
            search_valid = str(ctx.message.content[len(ctx.prefix+ctx.command.name)+1:].lower())
            if search_valid == "maps":
                await self.bot.say("Please actually search something")
            else:
                uri = "https://www.google.com/maps/search/"
                quary = str(ctx.message.content[len(ctx.prefix+ctx.command.name)+6:].lower())
                encode = urllib.parse.quote_plus(quary,encoding='utf-8',errors='replace')
                uir = uri+encode
                await self.bot.say(uir)
            #End of Maps
        #Start of generic search
        else:
            uri = "https://www.google.com/search?q="
            quary = str(ctx.message.content[len(ctx.prefix+ctx.command.name)+1:])
            encode = urllib.parse.quote_plus(quary,encoding='utf-8',errors='replace')
            uir = uri+encode
            async with aiohttp.get(uir, headers = option) as resp:
                test = str(await resp.content.read())
                query_find = re.findall(regex[1], test)
                if query_find == []:
                    query_find = re.findall(regex[2], test)
                    try:
                        if re.search("\/url?url=", query_find[0]) == True:
                            query_find = query_find[0]
                            m = re.search("\/url?url=", query_find)
                            query_find = query_find[:m.start()] + query_find[m.end():]
                            decode = self.unescape(query_find)
                            await self.bot.say("Here is your link: {}".format(decode))
                        else:
                            decode = self.unescape(query_find[0])
                            await self.bot.say("Here is your link: {}".format(decode))
                    except IndexError:
                        await self.bot.say("Your search yielded no results.")
                elif re.search("\/url?url=", query_find[0]) == True:
                    query_find = query_find[0]
                    m = re.search("\/url?url=", query_find)
                    query_find = query_find[:m.start()] + query_find[m.end():]
                    decode = self.unescape(query_find)
                    await self.bot.say("Here is your link: {}".format(decode))
                else:
                    query_find = query_find[0]
                    decode = self.unescape(query_find)
                    await self.bot.say("Here is your link: {} ".format(decode))
            #End of generic search

    def unescape(self, msg):
        regex = ["<br \/>", "(?:\\\\[rn])", "(?:\\\\['])", "%25", "\(", "\)"]
        subs = ["\n", "", "'", "%", "%28", "%29"]

        for i in range(len(regex)):
            sub = re.sub(regex[i], subs[i], msg)
            msg = sub
        return msg

    @commands.command(pass_context=True)
    async def avatar(self, ctx, user : discord.Member = None):
        """Check out someones avatar !
        Or just cheack out your own by simply doing avatar.
        Big thanks to TEDDY real og."""
        colour = ''.join([randchoice('0123456789ABCDEF') for x in range(6)])
        colour = int(colour, 16)        
        if user is None:
            user = ctx.message.author
        if user.avatar_url is None:
            await self.bot.reply("User has no avatar")
        em = discord.Embed(description="{0.name}'s avatar ==> Look at dat sexy avatar ;) ".format(user), colour=discord.Colour(value=colour))
        em.set_image(url=user.avatar_url)
        await self.bot.say(embed=em)

    @commands.command(pass_context=True)
    async def rps(self, ctx, choice : str):
        """Play rock paper scissors"""
        author = ctx.message.author
        rpsbot = {"rock" : ":moyai:",
           "paper": ":page_facing_up:",
           "scissors":":scissors:"}
        choice = choice.lower()
        if choice in rpsbot.keys():
            botchoice = randchoice(list(rpsbot.keys()))
            msgs = {
                "win": " You win {}!".format(author.mention),
                "square": " We're square {}!".format(author.mention),
                "lose": " You lose {}!".format(author.mention)
            }
            if choice == botchoice:
                await self.bot.say(rpsbot[botchoice] + msgs["square"])
            elif choice == "rock" and botchoice == "paper":
                await self.bot.say(rpsbot[botchoice] + msgs["lose"])
            elif choice == "rock" and botchoice == "scissors":
                await self.bot.say(rpsbot[botchoice] + msgs["win"])
            elif choice == "paper" and botchoice == "rock":
                await self.bot.say(rpsbot[botchoice] + msgs["win"])
            elif choice == "paper" and botchoice == "scissors":
                await self.bot.say(rpsbot[botchoice] + msgs["lose"])
            elif choice == "scissors" and botchoice == "rock":
                await self.bot.say(rpsbot[botchoice] + msgs["lose"])
            elif choice == "scissors" and botchoice == "paper":
                await self.bot.say(rpsbot[botchoice] + msgs["win"])
        else:
            await self.bot.say("Choose rock, paper or scissors.")

    @commands.command(aliases=["sw"], pass_context=True)
    async def stopwatch(self, ctx):
        """Starts/stops stopwatch"""
        author = ctx.message.author
        if not author.id in self.stopwatches:
            self.stopwatches[author.id] = int(time.perf_counter())
            await self.bot.say(author.mention + " Stopwatch started!")
        else:
            tmp = abs(self.stopwatches[author.id] - int(time.perf_counter()))
            tmp = str(datetime.timedelta(seconds=tmp))
            await self.bot.say(author.mention + " Stopwatch stopped! Time: **" + tmp + "**")
            self.stopwatches.pop(author.id, None)

    @commands.command()
    async def lmgtfy(self, *, search_terms : str):
        """Creates a lmgtfy link"""
        search_terms = escape_mass_mentions(search_terms.replace(" ", "+"))
        await self.bot.say("http://lmgtfy.com/?q={}".format(search_terms))


    @commands.command(pass_context=True, no_pm=True)
    async def userinfo(self, ctx, *, user: discord.Member=None):
        """Shows users's informations"""
        author = ctx.message.author
        server = ctx.message.server
    
        colour = ''.join([randchoice('0123456789ABCDEF') for x in range(6)])
        colour = int(colour, 16)

        if not user:
            user = author

        roles = [x.name for x in user.roles if x.name != "@everyone"]

        status = user.status

        joined_at = self.fetch_joined_at(user, server)
        since_created = (ctx.message.timestamp - user.created_at).days
        since_joined = (ctx.message.timestamp - joined_at).days
        user_joined = joined_at.strftime("%d %b %Y %H:%M")
        user_created = user.created_at.strftime("%d %b %Y %H:%M")

        created_on = "{}\n({} days ago)".format(user_created, since_created)
        joined_on = "{}\n({} days ago)".format(user_joined, since_joined)

        if user.game is None:
            game = "Playing ⇒ Bruh He aint playing shit"
        elif user.game.url is None:
            game = "Playing ⇒ {}".format(user.game)
        else:
            game = "Streaming ⇒  [{}]({})".format(user.game, user.game.url)

        if roles:
            roles = sorted(roles, key=[x.name for x in server.role_hierarchy
                                       if x.name != "@everyone"].index)
            roles = ", ".join(roles)
        else:
            roles = "Nothing to see here ¯\_(ツ)_/¯\n\n"

        if user.nick is None:
            user.nick = "No Nick :|"

        if roles is None:
            user.colour = discord.Colour(value=colour)

        if user.status == discord.Status.dnd:
            status == ":vpDnD: Dnd"
        if user.status == discord.Status.invisible:
            status == ":vpOffline: Dnd" 
        if user.status == discord.Status.online:
            status == ":vpOnline: Dnd"
        if user.status == discord.Status.idle:
            status == ":VPAway: Idle"

        data = discord.Embed(description=game, colour=user.colour)
        data.add_field(name="Status", value= " {} Is Currently {}".format(user.name, user.status))
        data.add_field(name="Joined Discord on", value=created_on)
        data.add_field(name="Nickname", value=user.nick)
        data.add_field(name="Joined this server on", value=joined_on)
        data.add_field(name="Roles", value=roles, inline=False)
        data.set_footer(text="Userinfo | User ID ⇒  " + user.id)


        if user.avatar_url:
            name = str(user)
            name = (name) if user.nick else name
            data.set_author(name=name, url=user.avatar_url)
            data.set_thumbnail(url=user.avatar_url)

        else:
            data.set_author(name=user.name)

        try:
            await self.bot.say(embed=data)
        except discord.HTTPException:
            await self.bot.say("I need the `Embed links` permission "
                               "to send this")

    @commands.command(pass_context=True, no_pm=True)
    async def serverinfo(self, ctx):
        """Shows server's informations"""
        server = ctx.message.server
        online = len([m.status for m in server.members
                      if m.status == discord.Status.online])
        idle = len([m.status for m in server.members
                      if m.status == m.status == discord.Status.idle])
        dnd = len([m.status for m in server.members
                      if m.status == discord.Status.dnd])
        total_users = len(server.members)
        text_channels = len([x for x in server.channels
                             if x.type == discord.ChannelType.text])
        voice_channels = len(server.channels) - text_channels
        passed = (ctx.message.timestamp - server.created_at).days
        created_at = ("Since {}. That's over {} days ago!"
                      "".format(server.created_at.strftime("%d %b %Y %H:%M"),
                                passed))

        colour = ''.join([randchoice('0123456789ABCDEF') for x in range(6)])
        colour = int(colour, 16)

        data = discord.Embed(
            description=created_at,
            colour=discord.Colour(value=colour))
        data.add_field(name="Region", value=str(server.region).upper())
        data.add_field(name="Users", value="{}({} Online Users)".format(total_users, online))
        data.add_field(name="Text Channels", value=text_channels)
        data.add_field(name="Voice Channels", value=voice_channels)
        data.add_field(name="Roles", value=len(server.roles))
        data.add_field(name="Owner", value=str(server.owner))
        data.add_field(name="Verification Level", value= str(server.verification_level))
        data.add_field(name="AFK Channel", value=str(server.afk_channel).upper())
        data.set_footer(text="Server ID ⇒  " + server.id)
        if len(str(server.emojis)) < 2024 and server.emojis:
            data.add_field(name="Emojis", value=" ".join([str(emoji) for emoji in server.emojis]), inline=False)
        elif len(str(server.emojis)) >= 2024:
            data.add_field(name="Emojis", value="**Error**: _What the fuck Too many fucken emojis !!_", inline=False)

        if server.icon_url:
            data.set_author(name=server.name, url=server.icon_url)
            data.set_thumbnail(url=server.icon_url)
        else:
            data.set_author(icon=server.icon_url, name=server.name)

        try:
            await self.bot.say(embed=data)
        except discord.HTTPException:
            await self.bot.say("I need the `Embed links` permission "
                               "to send this")

    @commands.command()
    async def urban(self, *, search_terms : str, definition_number : int=1):
        """Urban Dictionary search

        Definition number must be between 1 and 10"""
        # definition_number is just there to show up in the help
        # all this mess is to avoid forcing double quotes on the user
        search_terms = search_terms.split(" ")
        colour = ''.join([randchoice('0123456789ABCDEF') for x in range(6)])
        colour = int(colour, 16)
        try:
            if len(search_terms) > 1:
                pos = int(search_terms[-1]) - 1
                search_terms = search_terms[:-1]
            else:
                pos = 0
            if pos not in range(0, 11): # API only provides the
                pos = 0                 # top 10 definitions
        except ValueError:
            pos = 0
        search_terms = "+".join(search_terms)
        url = "http://api.urbandictionary.com/v0/define?term=" + search_terms
        try:
            async with aiohttp.get(url) as r:
                result = await r.json()
            if result["list"]:
                definition = result['list'][pos]['definition']
                example = result['list'][pos]['example']
                defs = len(result['list'])
                msg = ("***Definition #{} out of {}:\n***{}\n\n"
                       "**Example:\n**{}".format(pos+1, defs, definition,
                                                 example))
                msg = pagify(msg, ["\n"])
                for page in msg:
                    em = discord.Embed(description=page, colour=discord.Colour(value=colour))
                    em.set_footer(text="Your Urban", icon_url='https://cdn.discordapp.com/attachments/256904218571571200/257261567941410816/urban_sexy.jpg')
                    await self.bot.say(embed=em)
                
            else:
                await self.bot.say("Your search terms gave no results.")
        except IndexError:
            await self.bot.say("There is no definition #{}".format(pos+1))
        except:
            await self.bot.say("Error.")

    @commands.command(pass_context=True, no_pm=True)
    async def poll(self, ctx, *text):
        """Starts/stops a poll
        Usage example:
        poll Is this a poll?;Yes;No;Maybe
        poll stop"""
        message = ctx.message
        if len(text) == 1:
            if text[0].lower() == "stop":
                await self.endpoll(message)
                return
        if not self.getPollByChannel(message):
            check = " ".join(text).lower()
            if "@everyone" in check or "@here" in check:
                await self.bot.reply("Well At least you tried but i have counter messures against that ¯\_(ツ)_/¯")
                return
            p = NewPoll(message, self)
            if p.valid:
                self.poll_sessions.append(p)
                await p.start()
            else:
                await self.bot.say("poll question;option1;option2 (...)")
        else:
            await self.bot.say("A poll is already ongoing.")

    async def endpoll(self, message):
        if self.getPollByChannel(message):
            p = self.getPollByChannel(message)
            if p.author == message.author.id: # or isMemberAdmin(message)
                await self.getPollByChannel(message).endPoll()
            else:
                await self.bot.say("**Only Admins & Dangerous** can stop the poll.")
        else:
            await self.bot.say("No Ongoing poll.")

    def getPollByChannel(self, message):
        for poll in self.poll_sessions:
            if poll.channel == message.channel:
                return poll
        return False

    async def check_poll_votes(self, message):
        if message.author.id != self.bot.user.id:
            if self.getPollByChannel(message):
                    self.getPollByChannel(message).checkAnswer(message)

    def fetch_joined_at(self, user, server):
        """Just a special case for someone special :^)"""
        if user.id == "96130341705637888" and server.id == "133049272517001216":
            return datetime.datetime(2016, 1, 10, 6, 8, 4, 443000)
        else:
            return user.joined_at

class NewPoll():
    def __init__(self, message, main):
        self.channel = message.channel
        self.author = message.author.id
        self.client = main.bot
        self.poll_sessions = main.poll_sessions
        msg = message.content[6:]
        msg = msg.split(";")
        if len(msg) < 2: # Needs at least one question and 2 choices
            self.valid = False
            return None
        else:
            self.valid = True
        self.already_voted = []
        self.question = msg[0]
        msg.remove(self.question)
        self.answers = {}
        i = 1
        for answer in msg: # {id : {answer, votes}}
            self.answers[i] = {"ANSWER" : answer, "VOTES" : 0}
            i += 1

    async def start(self):
        msg = ":mailbox_with_mail: **POLL STARTED!**:mailbox_with_mail: \n\n**{}**\n\n".format(self.question)
        for id, data in self.answers.items():
            msg += "{}. *{}*\n".format(id, data["ANSWER"])
        msg += "\nType the freaken #To answer !"
        await self.client.send_message(self.channel, msg)
        await asyncio.sleep(settings["POLL_DURATION"])
        if self.valid:
            await self.endPoll()

    async def endPoll(self):
        self.valid = False
        msg = "**POLL ENDED!**\n\n{}\n\n".format(self.question)
        for data in self.answers.values():
            msg += "*{}* - {} votes\n".format(data["ANSWER"], str(data["VOTES"]))
        await self.client.send_message(self.channel, msg)
        self.poll_sessions.remove(self)

    async def check_reminders(self):
        while self is self.bot.get_cog("general"):
            to_remove = []
            for reminder in self.reminders:
                if reminder["FUTURE"] <= int(time.time()):
                    try:
                        await self.bot.send_message(discord.User(id=reminder["ID"]), "**Hey!!** {} You've asked me to remind you this \n{}".format(user.name, reminder["TEXT"]))
                    except (discord.errors.Forbidden, discord.errors.NotFound):
                        to_remove.append(reminder)
                    except discord.errors.HTTPException:
                        pass
                    else:
                        to_remove.append(reminder)
            for reminder in to_remove:
                self.reminders.remove(reminder)
            if to_remove:
                fileIO("data/remind/reminders.json", "save", self.reminders)
            await asyncio.sleep(5)

    def checkAnswer(self, message):
        try:
            i = int(message.content)
            if i in self.answers.keys():
                if message.author.id not in self.already_voted:
                    data = self.answers[i]
                    data["VOTES"] += 1
                    self.answers[i] = data
                    self.already_voted.append(message.author.id)
        except ValueError:
            pass

def check_file():
    f = 'data/away/away.json'
    if not dataIO.is_valid_json(f):
        dataIO.save_json(f, {})
        print('Creating default away.json...')

    weather = {}
    weather['WEATHER_API_KEY'] = ''
    weather['TIME_API_KEY'] = ''

    f = "data/weather/weather.json"
    if not dataIO.is_valid_json(f):
        print("Creating default weather.json...")
        dataIO.save_json(f, weather)

    data = {}
    f = "data/youtube/settings.json"
    if not dataIO.is_valid_json(f):
        print("Creating default settings.json...")
        dataIO.save_json(f, data)

    f = "data/remind/reminders.json"
    if not fileIO(f, "check"):
        print("Creating empty reminders.json...")
        fileIO(f, "save", [])




def check_folder():
    if not os.path.exists('data/seen'):
        print('Creating data/seen folder...')
        os.makedirs('data/seen')

    if not os.path.exists("data/moji"):
        print("Creating data/moji folder...")
        os.makedirs("data/moji")

    if not os.path.exists('data/away'):
        print('Creating data/away folder...')
        os.makedirs('data/away')

    if not os.path.exists("data/weather"):
        print("Creating data/weather folder...")
        os.makedirs("data/weather")

    if not os.path.exists("data/youtube"):
        print("Creating data/youtube folder...")
        os.makedirs("data/youtube")

    if not os.path.exists("data/remind"):
        print("Creating data/remind folder...")
        os.makedirs("data/remind")

def setup(bot):
    global logger
    check_folder()
    check_file()
    n = General(bot)
    logger = logging.getLogger("remindme")
    if logger.level == 0: # Prevents the logger from being loaded again in case of module reload
        logger.setLevel(logging.INFO)
        handler = logging.FileHandler(filename='data/remind/reminders.log', encoding='utf-8', mode='a')
        handler.setFormatter(logging.Formatter('%(asctime)s %(message)s', datefmt="[%d/%m/%Y %H:%M]"))
        logger.addHandler(handler)
    bot.add_listener(n.check_poll_votes, "on_message")
    bot.add_listener(n.listener, 'on_message')
    loop = asyncio.get_event_loop()
    loop.create_task(n.check_reminders())
    bot.add_cog(n)