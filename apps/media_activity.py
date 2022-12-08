import appdaemon.plugins.hass.hassapi as hass
import yaml
import time

class MediaActivity(hass.Hass):
    def initialize(self):

        # global variables
        self.set_current_activity()
        self.log(self.current_activity, level = "DEBUG")

        # Load media_activities.yaml
        with open('/config/media_activities.yaml') as conf_file:
            self.activity_conf = yaml.safe_load(conf_file);
            self.activities = self.activity_conf['activities']['living_room']

        # triggers
        self.activity_changer("input_text.lr_remote_activity",'state','off','roku', '')
        #self.listen_state(self.activity_changer, entity_id="input_text.lr_remote_activity")

    def set_current_activity(self):
        # Set a global tracking variable for the current media activity
        activity = self.entities.input_text.lr_remote_activity.state
        self.current_activity = activity
        
    def activity_changer(self, entity, attribute, old, new, kwargs):
        if old == new:
            return False

        self.log('Activity change from '+old+' to '+new, level = "INFO")

        if new not in self.activity_conf['activities']['living_room']:
            # if the requested activity isn't valid, reset the current activity tracker and return false
            self.set_current_activity(old)
            return False

        diffs = self.activity_diff_finder(self.activities[new], self.activities[old])

        self.command_sender(diffs)

    def activity_diff_finder(self, new_conf, old_conf):
        # This takes the config stub for the new activity and compares it to the old.
        # Returns a list of commands that need to run

        detected_diff = []

        for device in new_conf.keys():
            # Loop through all the things that are in the new activity's conf
            for desired_state in new_conf[device]['sequence']:
                #print(desired_state)
                current_state= next((seq for seq in old_conf[device]['sequence'] if seq['id'] == desired_state['id']),{})
                if ('state' in current_state and desired_state['state'] != current_state['state']) or 'state' not in current_state:
                    # If the state needs to change or there was no former state
                    if ('state' in current_state):
                        self.log(device+' should be '+desired_state['state']+' and is currently '+current_state['state'], level="DEBUG")
                    else:
                        self.log(device+' should be '+desired_state['state'], level='DEBUG')
                    
                    command = {
                        'device': new_conf[device]['device'],
                        'command': desired_state['command']
                    }
                    detected_diff.append(command)

                    # special check to see if there needs to be a pause before moving on
                    if 'wait' in desired_state:
                        self.log('A pause should go here', level="DEBUG")
                        detected_diff.append({ 'device': 'wait', 'command': 12 })
            
        return detected_diff

    def command_sender(self, commands):
        for command in commands:
            if command['device'] == 'wait':
                self.log("Wait encounted, sleeping for "+str(command['command'])+ " seconds")
                #time.sleep(command['command'])
            else:
                # send command via HA to the remote
                self.log("Sending "+str(command['command'])+" sent to "+str(command['device']))
