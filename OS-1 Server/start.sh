#!/bin/bash
LOG_DIR=./log
USER=deploy
#nohup python tools/asr_server.py >asr.log 2>&1 &
#nohup python tools/vad_server.py >vad.log 2>&1 &
#nohup python tools/tts_server.py >tts.log 2>&1 &
nohup python image_server.py >$LOG_DIR/image.log 2>&1 &
nohup python audio_server_v2.py >$LOG_DIR/audio.log 2>&1 &
nohup python msg_server.py >$LOG_DIR/msg.log 2>&1 &
nohup python chatbot_server.py >$LOG_DIR/chatbot.log 2>&1 &
nohup python active_chatbot_server.py >$LOG_DIR/active_chatbot.log 2>&1 &
nohup python data_server.py >$LOG_DIR/server.log 2>&1 &
nohup python context_cron_task.py >$LOG_DIR/context_cron_task.log 2>&1 &
nohup python conversation_cron_task.py >$LOG_DIR/conversation_cron_task.log 2>&1 &
nohup python scripts/conversation_visualization.py >$LOG_DIR/visual.log 2>&1 &
nohup python -m llava.serve.controller --host 0.0.0.0 --port 10000 >$LOG_DIR/llava.log 2>&1 &

#docker-compose up -d

# proxy
if ! pgrep -x "frpc" > /dev/null
then
    nohup ~/frp/frpc -c ~/frp/frpc.ini >$LOG_DIR/frp.log 2>&1 &
    echo "frpc started."
else
    echo "frpc is already running."
fi

nohup python system_monitor.py --start_all >$LOG_DIR/monitor.log 2>&1 &
