#!/bin/bash

script_version="v0.4"
script_verbose=true
script_debug=false
p_script="false"

#usedlog="logfile" #logfile / logsystem / lognone
usedlog="logsystem" #logfile / logsystem / lognone
#usedlog="lognone" #logfile / logsystem / lognone
LOGFILENAME="wled_preset_change.log"
#LOGFILE="${LOGPATH}/${LOGFILENAME}"
LOG_TAG="wled_preset_change"


IfIpTrue=false
wled_set_preset=0
wled_set_on=true
wled_set_brightness=0
wled_device="192.168.1.1"

#wled_set_preset=1
#wled_set_on=true
#wled_set_brightness=255
#wled_device="192.168.188.153"

# COLORS
CSI="$(printf '\033')["    # Control Sequence Introducer

black_text="${CSI}30m"     # Black
red_text="${CSI}31m"       # Red
green_text="${CSI}32m"     # Green
yellow_text="${CSI}33m"    # Yellow
blue_text="${CSI}34m"      # Blue
magenta_text="${CSI}35m"   # Magenta
cyan_text="${CSI}36m"      # Cyan
white_text="${CSI}37m"     # White

b_black_text="${CSI}90m"   # Bright Black
b_red_text="${CSI}91m"     # Bright Red
b_green_text="${CSI}92m"   # Bright Green
b_yellow_text="${CSI}93m"  # Bright Yellow
b_blue_text="${CSI}94m"    # Bright Blue
b_magenta_text="${CSI}95m" # Bright Magenta
b_cyan_text="${CSI}96m"    # Bright Cyan
b_white_text="${CSI}97m"   # Bright White

reset_text="${CSI}0m"      # Reset to default
clear_line="${CSI}0K"      # Clear the current line to the right to wipe any artifacts remaining from last print

# STYLES
bold_text="${CSI}1m"
blinking_text="${CSI}5m"
dim_text="${CSI}2m"

createDirectory() {
   mkdir -p "$1"
}

wled_ip_check(){
    local TestIP
    TestIP=$1
    #ip=192.168.188.153
    #ip=1.2.3.4
#    echo "WLED_Device_IP: $TestIP"
    if [[ $TestIP =~ ^192+\.168+\.[0-9]+\.[0-9]+$ ]]; then
        IfIpTrue=true
    else
        IfIpTrue=false
    fi
}

ShowVersion() {
    tM_msg="${bold_text}${green_text}wled_preset_cange.sh${reset_text} ${b_white_text}${script_version}${reset_text}"
	echo "${tM_msg}" "${tM_log}"
    tM_msg="${bold_text}${green_text}===========================${reset_text}"
	echo "${tM_msg}" "${tM_log}"
    exit 0
}

DisplayHelp() {
    cat << EOM
::: HELP =================================================================================================
:::   wled_preset_cange.sh is a helper script to control WLED devices via command line
:::
::: USAGE ================================================================================================
:::   ./wled_preset_cange.sh -d=192.168.1.123 -p=1              (set preset 1 on WLED Device 192.168.1.123)
:::   ./wled_preset_cange.sh -d=192.168.1.123 -0                (switch leds off on WLED Device 192.168.1.123)
:::   ./wled_preset_cange.sh -d=192.168.1.123 -b=100            (set the brightness to 100 from all leds on WLED Device)
:::   ./wled_preset_cange.sh -d=192.168.1.123 -p=1 -b=100 -V    (WLED Device 192.168.1.123, preset 1, bright=100, verbose)
:::   ./wled_preset_cange.sh --version
:::   ./wled_preset_cange.sh --help
:::
::: PARAMETERS ==============================================================================================
:::	  -d=[IP],--device=[IP]			IP from a WLED Device
:::   -p=[num],--preset=[num]		id from a preset in the WLED Device
:::   -b=[0-255],--bright=[0-255]	set the brightness from all leds on WLED Device
:::
::: Options ==============================================================================================
:::   -0,--off	     				switch all leds off
:::   -1,--on   					switch all leds on
:::   -V,--verbose					VerboseMode (Show what this script do)
:::
::: Options *cannot be combined with other options* ======================================================
:::   -v, --version           		show wled_preset_cange.sh version info
:::   -h, --help              		display this help text
:::

EOM
    exit 0

}

# systemd-compatible logging feature
log_message() {
    # use the logger only to avoid distorting the output with replaced commands.
#    logger -t "$LOG_TAG" "$(date '+%Y-%m-%d %H:%M:%S') - $1"
    logger -t "$LOG_TAG" "$1"
    #echo "$(date '+%b %d %T') $LOG_TAG $1" | ccze -A --plugin=syslog | tee -a dell_fans.log
}

tModeDebug() {
    local msgId
    local msgText
    local dtstart
	msgId=$1
	msgText=$2

	if [ "$msgId" = "1" ]; then #error
		msgTyp="[${red_text}ERROR${reset_text}]"
	elif [ "$msgId" = "2" ]; then #debug
		msgTyp="[${yellow_text}DEBUG${reset_text}]"
	elif [ "$msgId" = "3" ]; then #verbose
		msgTyp="[${cyan_text}VERBOSE${reset_text}]"
	else #info
		msgTyp="[${green_text}INFO${reset_text}]"
	fi

	#dtstart=$(date +"%d-%b-%Y %T")
	dtstart=$(date +"%b %d %T")

    if [ "$script_verbose" = true ] && [ "$msgId" = "3" ]; then
        echo "${cyan_text}${dtstart}${reset_text} ${blue_text}${LOG_TAG}${reset_text} ${msgTyp}: ${msgText}"
        if [ "$usedlog" = "logfile" ]; then
            echo "${cyan_text}${dtstart}${reset_text} ${blue_text}${LOG_TAG}${reset_text} ${msgTyp}: ${msgText}" >> $LOGFILE
        fi
        if [ "$usedlog" = "logsystem" ]; then
            log_message "${msgTyp}: ${msgText}"
        fi
    fi

    if [ "$script_debug" = true ] && [ "$msgId" = "2" ]; then
        echo "${cyan_text}${dtstart}${reset_text} ${blue_text}${LOG_TAG}${reset_text} ${msgTyp}: ${msgText}"
        if [ "$usedlog" = "logfile" ]; then
            echo "${cyan_text}${dtstart}${reset_text} ${blue_text}${LOG_TAG}${reset_text} ${msgTyp}: ${msgText}" >> $LOGFILE
        fi
        if [ "$usedlog" = "logsystem" ]; then
            log_message "${msgTyp}: ${msgText}"
        fi
    fi

    if [ "$msgId" = "1" ]; then
        echo "${cyan_text}${dtstart}${reset_text} ${blue_text}${LOG_TAG}${reset_text} ${msgTyp}: ${msgText}"
        if [ "$usedlog" = "logfile" ]; then
            echo "${cyan_text}${dtstart}${reset_text} ${blue_text}${LOG_TAG}${reset_text} ${msgTyp}: ${msgText}" >> $LOGFILE
        fi
        if [ "$usedlog" = "logsystem" ]; then
            log_message "${msgTyp}: ${msgText}"
        fi
    fi

    if [ "$msgId" = "0" ]; then
        echo "${cyan_text}${dtstart}${reset_text} ${blue_text}${LOG_TAG}${reset_text} ${msgTyp}: ${msgText}"
        if [ "$usedlog" = "logfile" ]; then
            echo "${cyan_text}${dtstart}${reset_text} ${blue_text}${LOG_TAG}${reset_text} ${msgTyp}: ${msgText}" >> $LOGFILE
        fi
        if [ "$usedlog" = "logsystem" ]; then
            log_message "${msgTyp}: ${msgText}"
        fi
    fi

}


checkLogfileFile() {
# check existence of logfile
	#dtstart=$(date +"%d-%b-%Y %T")
	dtstart=$(date +"%b %d %T")
    if [ -d "$LOGPATH" ]; then
        tM_msg="${b_yellow_text}LOGPATH${reset_text} (${cyan_text}$LOGPATH${reset_text}) ${b_yellow_text}does exist.${reset_text}"
        tModeDebug "2" "${tM_msg}"
        #echo "$LOGPATH does exist."
    else
        createDirectory "$LOGPATH"
        tM_msg="${b_yellow_text}LOGPATH${reset_text} (${cyan_text}$LOGPATH${reset_text}) ${b_yellow_text}not exist. create the LOGPATH${reset_text}"
        tModeDebug "2" "${tM_msg}"
        #echo "$LOGPATH created"
    fi



	# if not exist create logfile
	if [ ! -f "$LOGFILE" ] || [ ! -r "$LOGFILE" ]; then
        tM_msg="${b_yellow_text}LOGFILE${reset_text} (${cyan_text}$LOGFILE${reset_text}) ${b_yellow_text}not exist. create the LOGFILE${reset_text}"
        tModeDebug "2" "${tM_msg}"

		echo "${cyan_text}${dtstart}${reset_text} ${blue_text}${LOG_TAG}${reset_text} [${yellow_text}DEBUG${reset_text}]: ${tM_msg}" > $LOGFILE

		# check if logfile write susseful
		if [ ! -f "$LOGFILE" ] || [ ! -r "$LOGFILE" ]; then
			tM_msg="${red_text}write error:${reset_text} (${cyan_text}$LOGFILE${reset_text}) ${red_text}not created!${reset_text}"
			tModeDebug "1" "${tM_msg}"
			exit 1
		else
			tM_msg="${b_yellow_text}create LOGFILE${reset_text} (${cyan_text}$LOGFILE${reset_text}) ${b_green_text}successful${reset_text}"
            tModeDebug "2" "${tM_msg}"
            echo "${cyan_text}${dtstart}${reset_text} ${blue_text}${LOG_TAG}${reset_text} [${yellow_text}DEBUG${reset_text}]: ${tM_msg}" >> $LOGFILE
		fi
	else
		tM_msg="${b_yellow_text}LOGFILE${reset_text} (${cyan_text}$LOGFILE${reset_text}) ${b_green_text}found${reset_text}"
        tModeDebug "2" "${tM_msg}"
        echo "${cyan_text}${dtstart}${reset_text} ${blue_text}${LOG_TAG}${reset_text} [${yellow_text}DEBUG${reset_text}]: ${tM_msg}" >> $LOGFILE
	fi
}



main(){
    # run from wled_start.sh or direct
    if [ "$p_script" = true ]; then
        LOGPATH="/var/log/wled/"
    else
        LOGPATH="/home/$USER/var/log/wled/"
    fi
	log_date_start=$(date +"%b_%d_%Y")
LOGFILE="${LOGPATH}${log_date_start}_${LOGFILENAME}"

checkLogfileFile


    tM_msg="${b_yellow_text}script_verbose: ${script_verbose}${reset_text}"
    tModeDebug "2" "${tM_msg}"
    tM_msg="${b_yellow_text}p_script: ${p_script}${reset_text}"
    tModeDebug "2" "${tM_msg}"
    tM_msg="${b_yellow_text}usedlog: ${usedlog}${reset_text}"
    tModeDebug "2" "${tM_msg}"
    tM_msg="${b_yellow_text}LOGFILE: ${LOGFILE}${reset_text}"
    tModeDebug "2" "${tM_msg}"
    #error
    #tM_msg="${red_text}error message${reset_text}"
    #tModeDebug "1" "${tM_msg}"

    #debug
    #tM_msg="${b_yellow_text}debug message${reset_text}"
    #tModeDebug "2" "${tM_msg}"

    #verbose
    #tM_msg="\n${yellow_text}verbose message${reset_text}"
    #tModeDebug "3" "${tM_msg}"

    #info
    #tM_msg="\n${green_text}info message${reset_text}"
    #tModeDebug "0" "${tM_msg}"



    #echo "WLED-Device: http://$wled_device"
    tM_msg="${green_text}WLED-Device: http://${wled_device}${reset_text}"
    tModeDebug "0" "${tM_msg}"

    wled_ip_check "$wled_device"
    #echo "Check Device IP..."
    tM_msg="${green_text}Check Device IP...${reset_text}"
    tModeDebug "3" "${tM_msg}"
    if [ "$IfIpTrue" = "true" ]; then
        if [ "$script_verbose" = "true" ]; then
            #echo "success! $ip is a valid ip"
            tM_msg="${green_text}success! $ip is a valid ip${reset_text}"
            tModeDebug "3" "${tM_msg}"
        fi
    else
        #echo "fail! $ip is NOT a valid ip"
        #echo "script exit!"
        tM_msg="${red_text}fail! $ip is NOT a valid ip${reset_text}"
        tModeDebug "1" "${tM_msg}"
        tM_msg="${red_text}script exit!${reset_text}"
        tModeDebug "1" "${tM_msg}"
        exit 1
    fi


    #echo "Check Device Response..."
    tM_msg="${green_text}Check Device Response...${reset_text}"
    tModeDebug "3" "${tM_msg}"
    cmd_var="http://$wled_device/json/state"
    #echo ""

    status_code=$(curl --write-out %{http_code} --silent --output /dev/null $cmd_var)
    if [[ "$status_code" -ne 200 ]] ; then
        #echo "WLED Device problem (Error code:$status_code)"
        tM_msg="${red_text}WLED Device problem (Error code:$status_code)${reset_text}"
        tModeDebug "1" "${tM_msg}"
        tM_msg="${red_text}script exit!${reset_text}"
        tModeDebug "1" "${tM_msg}"
        exit 1
    else
        #echo "WLED Device ready (Error code:$status_code)"
        tM_msg="${green_text}WLED Device ready (Error code:$status_code)${reset_text}"
        tModeDebug "3" "${tM_msg}"
    fi

    cmd_var="http://$wled_device/json/state"
    #echo ""


    tM_msg="${green_text}Send WLED Changes...${reset_text}"
    tModeDebug "3" "${tM_msg}"

    if [ "$wled_set_preset" -gt 0 ]; then
        pre_var=$wled_set_preset
        #curl -s "$cmd_var" -d {"ps":$pre_var} -H "Content-type: application/json"
        #curl -X POST "$cmd_var" -d {"ps":$wled_set_preset} -H "Content-type: application/json" 2>&1
        test_http_code=$(curl --silent -X POST $cmd_var -d {"ps":$wled_set_preset} -H "Content-type: application/json")
        #test_http_code=$(curl --write-out %{http_code} --silent --output /dev/null -X POST -H "Content-Type: application/json" -d '{"ps":$pre_var}' $cmd_var)
        #test_http_code=$(curl -s -o /dev/null -w "%{http_code}" -X POST -H "Content-Type: application/json" -d '{"ps":$pre_var}' "$cmd_var")
        #curl -s -o /dev/null -w "%{http_code}" -X POST -H "Content-Type: application/json" -d '{"key": "value"}' https://api.example.com/endpoint
        tM_msg="${yellow_text}WLED Load Preset: ${pre_var} ${test_http_code} ${reset_text}"
        tModeDebug "0" "${tM_msg}"
    fi
    if [ "$wled_set_preset" = 0 ]; then
        wled_set_on=false
        wled_set_brightness=0
        #pre_var=$wled_set_preset
        #test_http_code=$(curl --silent -X POST $cmd_var -d {"ps":$wled_set_preset} -H "Content-type: application/json")
        #tM_msg="${yellow_text}WLED Load Preset: ${pre_var} ${test_http_code} ${reset_text}"
        #tModeDebug "3" "${tM_msg}"
    fi


    on_var="$wled_set_on"
    if [ "$on_var" = true ]; then
        set_on=$(curl --silent -X POST "$cmd_var" -d {"on":true} -H "Content-type: application/json")
        tM_msg="${yellow_text}WLED turn on ${set_on}${reset_text}"
        tModeDebug "0" "${tM_msg}"
    elif [ "$on_var" = false ]; then
        set_off=$(curl --silent -X POST "$cmd_var" -d {"on":false} -H "Content-type: application/json")
        tM_msg="${yellow_text}WLED turn off ${set_off}${reset_text}"
        tModeDebug "0" "${tM_msg}"
    fi

    if [ "$wled_set_brightness" -gt 0 ]; then
        bri_var="$wled_set_brightness"
        set_bri=$(curl --silent -X POST "$cmd_var" -d {"bri":$bri_var} -H "Content-type: application/json")
        tM_msg="${yellow_text}WLED set Brightness: $bri_var ${set_bri}${reset_text}"
        tModeDebug "0" "${tM_msg}"
    fi
    if [ "$wled_set_brightness" = 0 ]; then
        bri_var="$wled_set_brightness"
        set_bri=$(curl --silent -X POST "$cmd_var" -d {"bri":$bri_var} -H "Content-type: application/json")
        tM_msg="${yellow_text}WLED set Brightness: $bri_var ${set_bri}${reset_text}"
        tModeDebug "0" "${tM_msg}"
    fi


    #echo "Preset-Nr: $2"
    #echo "cmd_var: $cmd_var"
    #echo "pre_var: $pre_var"
    #echo "urlvar: $urlvar"
    #echo "idvar: $idvar"
    #echo ""

    tM_msg="${green_text}script done.${reset_text}"
    tModeDebug "3" "${tM_msg}"

}

# As long as there is at least one more argument, keep looping
# Process all options (if present)
#while [ "$#" -gt 0 ]; do
for i in "$@"; do
    case "$i" in
        -h|--help)
          DisplayHelp
          exit 0
          ;;
        -v|--version)
          ShowVersion
          exit 0
          ;;
        -V|--verbose)
          script_verbose=true
          ;;
        -D|--debug)
          script_debug=true
          script_verbose=true
          ;;
        -p=*|--preset=*)
          wled_set_preset="${i#*=}"
          shift # past argument=value
          ;;
        -1|--on)
          wled_set_on=true
          shift # past argument=value
          ;;
        -0|--off)
          wled_set_on=false
          shift # past argument=value
          ;;
        -b=*|--bright=*)
          wled_set_brightness="${i#*=}"
          shift # past argument=value
          ;;
        -d=*|--device=*)
          wled_device="${i#*=}"
          shift # past argument=value
          ;;
        --p_script)
          p_script="true"
          script_verbose=false
          script_debug=false
          shift # past argument=value
          ;;
        *)
          DisplayHelp
          ;;
    esac
    #shift
done

main
