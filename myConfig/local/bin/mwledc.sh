#!/bin/bash
if [ ${#*} != 0 ];
then
    wledcom="$*"
else
    echo "mwledc.sh [BRIGHT],[WLED-IP],[WLED-Preset-ID] [BRIGHT],[WLED-IP],[WLED-Preset-ID]"
    echo "mwledc.sh 192.168.188.92,1,10 192.168.188.153,2,10"
    exit 255
fi

#AllServers=(
#    "vmkm13, 172.16.39.71"
#    "vmkm14, 172.16.39.72"
#    "vmkm15, 172.16.39.84"
#    "vmkw51, 172.16.39.73"
#    "vmkw52, 172.16.39.74"
#    "vmkw53, 172.16.39.75"
#)
#echo $wledcom
#echo "Number of arguments=${#*}"

   for i in "$@"
   do
   #echo "$i"
   #echo ${i#*,}

   IN=$i
   arrIN=(${IN//,/ })
   wledhost=${arrIN[0]}
   wledpreset=${arrIN[1]}
   wledbright=${arrIN[2]}
    if [ "$wledbright" = "" ]; then
        wledbright=255;
    fi
   echo "wled=$wledhost preset=$wledpreset bright=$wledbright --p_script"
#   wledhost=$(echo "$wcom" | awk -F',' '{ print $1 }')
#   wledpreset=$(echo "$wcom" | awk -F',' '{ print $2 }')
#   echo "wledhost=$wledhost wledpreset=$wledpreset"
#   echo ""
   #wled_preset_change.sh $wledhost $wledpreset
   wled_preset_change.sh -d=$wledhost -p=$wledpreset -b=$wledbright "--p_script"
   #wled_preset_change.sh -d=$wledhost -p=$wledpreset -b=$wledbright -D
   done;
#for wcom in "${wledcom[@]}"; do
#    wledhost=$(echo "$wcom" | awk -F',' '{ print $1 }')
#    wledpreset=$(echo "$wcom" | awk -F',' '{ print $2 }')
#    echo "wledhost=$wledhost wledpreset=$wledpreset"
#    echo ""
#    ./wled_preset_change.sh $wledhost $wledpreset

#done

