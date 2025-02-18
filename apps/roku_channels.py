import appdaemon.plugins.hass.hassapi as hass
from collections import OrderedDict
import urllib
import json
import time
import xmltodict
import re

class RokuChannels(hass.Hass):
    def initialize(self):
        self.roku_channel_def = {} # Channel dict that equates name to channel ID
        self.roku_channel_list = [] # List of channel names from the roku endpoint
        self.ha_channel_list = [] # The list currently stored in HA
        self.channel_url = "http://"+self.args['roku_ip']+":8060/query/apps"
        self.change_lock = False
        
        self.run_every(self.update_channels, "now", 15)

        # TODO: For each channel, set up a listener
        # TODO: Remove this listener
        self.listen_state(self.channel_changer, entity_id="input_select.roku_channels")

        # Listen for changes the the input_select.lr_channel_shortcut entity
        self.listen_state(self.channel_finder, entity_id="input_text.lr_channel_shortcut")

        #print(json.dumps(self.roku_channel_def, indent=2))
        #print(json.dumps(self.ha_channel_list, indent=2))

    def channel_finder(self, entity, attribute, old, new, kwargs):
        """ Use the value of the lr_channel_shortcut input_text to find the channel ID that wildcard matches the channel name """
        self.log("Channel finder called with "+new)

        # Get the current value of the input_text
        channel_search_term = self.entities.input_text.lr_channel_shortcut.state

        # If the channel_search_term is empty or less than 3 characters, return
        if len(channel_search_term) < 3:
            return

        # The channel_search_term is the first characters of the channel name, find the value in self.ha_channel_list that matches
        for channel_name in self.ha_channel_list:
            # If the channel name matches the search term, set the input_select to that channel and break
            if bool(re.match(channel_search_term, channel_name, re.I)):
                self.log("Found channel "+channel_name)
                self.set_state("input_select.roku_channels", state=channel_name)
                break


    def update_channels(self, kwargs):
        # Update the roku_channel input_select every 5 minutes

        # read in the channel list
        self.load_roku_channels()

        # get current list from home assistant
        self.load_ha_channels()

        # diff with the new channel list
        if self.roku_channel_list != self.ha_channel_list:
            # If there's a difference update home assistant

            self.call_service("input_select/set_options", entity_id="input_select.roku_channels", options=self.roku_channel_list)
            self.set_input_select()
            self.log('Channels Updated')

        self.create_switches()

        self.set_input_select()

    def set_input_select(self):
        # Set the default option for the input select
        current_app = self.entities.media_player.living_room.attributes.app_name

        # If we see an app that's not in the list, set it to Home
        if current_app not in self.roku_channel_list:
            self.log("Saw invalid app "+current_app+". Defaulting to Home.")
            return
        else:
            self.log("Saw current app as "+current_app)

        try:
            self.call_service("input_select/select_option", entity_id="input_select.roku_channels", option=current_app)
        except Exception:
            self.error("Unable to set input_select to "+current_app)
            self.error("generic exception: " + traceback.format_exc())

    def create_switches(self):
        # Create a switch for each channel
        for channel in self.roku_channel_list:
            self.log("Creating switch for "+channel)
            channel_name = channel.split('-', 1)[0].strip()
            entity_name = "switch.lr_roku_"+channel_name.lower().replace(" ", "_")

            # Test to see with the switch entity exists
            if not self.entity_exists(entity_name):
                # Create a switch entity for each channel
                self.log("Creating switch entity for "+entity_name)
                self.set_state(entity_name, state="off", attributes={"friendly_name": "Roku "+channel_name})
    
    def load_roku_channels(self):
        # Get file from url
        try:
            channels = urllib.request.urlopen(self.channel_url, timeout=5)
        except Exception:
            import traceback
            self.error('Unable to get channel list from Roku')
            self.error('generic exception: ' + traceback.format_exc())
        else:
            raw_channels = xmltodict.parse(channels.read())
            self.roku_channel_def = {app['#text'] : app['@id'] for app in raw_channels['apps']['app']}
            self.roku_channel_def = OrderedDict(sorted(self.roku_channel_def.items()))
            self.roku_channel_list = list(self.roku_channel_def.keys())
            self.roku_channel_list.insert(0, "Home")

    def load_ha_channels(self):
        self.ha_channel_list = self.entities.input_select.roku_channels.attributes.options

        if len(self.ha_channel_list) < 2:
            self.log("Short channel list detected, locking channel change")
            self.change_lock = True

    def channel_changer(self, entity, attribute, old, new, kwargs):
        # TODO: Needs to reset switches
        # TODO: Send Off, Record, OTA, and Switch to the media_activity app
        self.log("channel changer called with "+new+" and "+old)
        # catch the roku_channel input select changing
        if (self.change_lock == True):
            self.log("Channel change blocked by update lock")
            self.change_lock = False
        else:
            self.call_service("media_player/select_source", entity_id="media_player.living_room", source=new)