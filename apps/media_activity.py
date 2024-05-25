import appdaemon.plugins.hass.hassapi as hass
import yaml
import time
import urllib

class MediaActivity(hass.Hass):
    def initialize(self):

        # global variables
        self.set_current_activity()
        self.log(self.current_activity, level = "DEBUG")

        # Roku ECP API URL
        self.roku_url = "http://"+self.args["roku_ip"]+":8060/"

        # Load media_activities.yaml
        with open('configs/media_sequences.yaml') as conf_file:
            self.activity_conf = yaml.safe_load(conf_file)
            self.activities = self.activity_conf['activities']['living_room']

        # Load the remote config
        with open('/homeassistant/.storage/broadlink_remote_ec0baea35ab2_codes') as conf_file:
            self.remote_conf = yaml.safe_load(conf_file)

        # triggers
        self.listen_state(self.activity_changer, entity_id="input_text.lr_remote_activity")
        self.listen_event(self.button_press, "remote_button_press")

    def set_current_activity(self):
        # Set a global tracking variable for the current media activity
        activity = self.entities.input_text.lr_remote_activity.state
        self.current_activity = activity
        
    def activity_changer(self, entity, attribute, old, new, kwargs):
        if old == new:
            return False

        self.log('Activity change from '+old+' to '+new, level = "INFO")

        if new in self.activity_conf['activities']['living_room']:
            diffs = self.activity_diff_finder(self.activities[new], self.activities[old])
            self.command_sender(diffs)
        else:
            self.error('Invalid activity: '+new)
            return False

    def activity_diff_finder(self, new_conf, old_conf):
        # This takes the config stub for the new activity and compares it to the old.
        # Returns a list of commands that need to run

        detected_diff = []

        for device in new_conf.keys():
            # Loop through all the things that are in the new activity's conf
            for desired_state in new_conf[device]['sequence']:
                current_state= next((seq for seq in old_conf[device]['sequence'] if seq['id'] == desired_state['id']),{})
                if ('state' in current_state and desired_state['state'] != current_state['state']) or 'state' not in current_state:
                    # If the state needs to change or there was no former state
                    if ('state' in current_state):
                        self.log(device+' should be '+desired_state['state']+' and is currently '+current_state['state'], level="DEBUG")
                    else:
                        self.log(device+' should be '+desired_state['state'], level='DEBUG')
                    
                    command = {
                        'device_id': new_conf[device]['device_id'],
                        'button_id': desired_state['button_id']
                    }
                    detected_diff.append(command)

        return detected_diff

    def button_press(self, event, data, kwargs):
        self.log("Event: "+event, level = "DEBUG")

        # Support for pre-scripted sequences
        commands = []
        if data["device_id"] == "sequence":
            # get the sequence from the config
            sequence = self.activity_conf['sequences'][data["button_id"]]
            self.log("Sequence: "+str(sequence), level = "DEBUG")

            for command in sequence:
                # loop through the sequence and add the commands to the list
                # I zero-indexed the repeats for grammatical purposes, so add one to make it work in loops
                repeats = command.get("repeats", 0)  # Get the number of repeats, default to 0 if not present
                repeats += 1
                for i in range(repeats):
                    commands.append({"device_id": command["device_id"], "button_id": command["button_id"]})
        # Non-sequence commands
        else:
            # I zero-indexed the repeats for grammatical purposes, so add one to make it work in loops
            repeats = data.get("repeats", 0)  # Get the number of repeats, default to 0 if not present
            repeats += 1 # add one to the repeats because it's always one less than it should be

            # If repeating more than once, send the command multiple times via the command_sender's list support
            for i in range(repeats):
                commands.append({ "device_id": data["device_id"], "button_id": data["button_id"]})

        self.command_sender(commands)

    def command_sender(self, commands):
        self.log("Issuing {} commands".format(len(commands)), level = "DEBUG")
        for command in commands:
            device = str(command['device_id'])
            command = str(command['button_id'])
            self.log("Sending command: "+command+" to "+device)
            
            # Call the appropriate function to send the command
            if device == "roku":
                self.roku_sender(command)
            else:
                self.ir_sender(device, command)

            if device == "visiotv" and command == "powerOn":
                self.log("Pausing for the TV to be stupid.")
                time.sleep(12)

            time.sleep(0.33)

    def ir_sender(self, device_id, button_id, unit_id = "living_room"):
        # Send an IR command to a device
        # device_id is the ID of the device in the harmony config file
        # button_id is the ID of the button in the harmony config file
        # repeats is the number of times to send the command

        entity_id = "remote."+unit_id+"_mantle_ir_remote"

        if device_id in self.remote_conf['data'] and button_id in self.remote_conf['data'][device_id]:
            self.log("Sending IR command: "+button_id+" to "+device_id, level = "DEBUG")
            self.call_service("remote/send_command", entity_id=entity_id, device=device_id, command=button_id)
        else:
            self.error("Invalid button: " + button_id)

    def roku_sender(self, button_id, unit_id = "living_room"):
        # Send a Roku command to the Roku
        # button_id is the ID of the button in the Roku API
        # repeats is the number of times to send the command

        # From: https://www.home-assistant.io/integrations/roku/
        available_buttons = [
            "back",
            "down",
            "enter",
            "forward",
            "home",
            "info",
            "left",
            "play",
            "replay",
            "reverse",
            "right",
            "select",
            "up",
            "volume_mute"
        ]

        entity_id = "remote."+unit_id

        if button_id in available_buttons:
            self.log("Sending Roku command: "+button_id, level = "DEBUG")
            self.call_service("remote/send_command", entity_id=entity_id, command=button_id)
            
            # To use the roku API directly:
            # You'll need to change available buttons to match: https://developer.roku.com/docs/developer-program/dev-tools/external-control-api.md#keypress-key-values
            #self.log("Sending Roku command: "+button_id+" to "+self.roku_url+"keypress/"+button_id)
            #try:
            #    urllib.request.urlopen(self.roku_url+"keypress/"+button_id, timeout=1)
            #except Exception:
            #    import traceback
            #    self.error('Unable to send keypress to Roku')
            #    self.error('generic exception: ' + traceback.format_exc())
            #urllib.request.urlopen(self.roku_url+"keypress/"+button_id, timeout=1)
        else:
            self.error("Invalid button: " + button_id)