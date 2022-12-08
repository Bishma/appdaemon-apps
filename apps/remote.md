# Set Channels

* On load
  * Read activity yaml into ram
* Every 5 Min
  * Get Channel List 
    * Set input_select in HA
    * Store in variable
    * Compare before updating or otherwise avoid updating when unneeded
* On Activity Change
  * Compare last activity to new activity states
    * diff the 2 activity configs
    * change states per the diff
* Set Roku Channel
  * use mediaplayer.select_source to change the channel