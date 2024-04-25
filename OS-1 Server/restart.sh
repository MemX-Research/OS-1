LOG_DIR=./log
USER=deploy

#for process in asr_server.py vad_server.py tts_server.py data_server.py chatbot_server.py active_chatbot_server.py image_server.py audio_server.py msg_server.py context_cron_task.py conversation_cron_task.py multiprocessing.resource_tracker multiprocessing.spawn
for process in data_server.py chatbot_server.py active_chatbot_server.py image_server.py audio_server_v2.py msg_server.py context_cron_task.py conversation_cron_task.py conversation_visualization.py multiprocessing.resource_tracker multiprocessing.spawn
#for process in chatbot_server.py active_chatbot_server.py
do
  echo $process
  pid=$(ps aux | grep $USER | grep $process | grep -v grep | awk '{print $2}')
  if [ -n "$pid" ]
  then
      echo "进程已存在，进程ID为$pid，正在杀死进程..."
      kill -9 $pid
  else
      echo "进程不存在"
  fi
done

nohup python image_server.py >$LOG_DIR/image.log 2>&1 &
nohup python audio_server_v2.py >$LOG_DIR/audio.log 2>&1 &
nohup python msg_server.py >$LOG_DIR/msg.log 2>&1 &
nohup python chatbot_server.py >$LOG_DIR/chatbot.log 2>&1 &
nohup python active_chatbot_server.py >$LOG_DIR/active_chatbot.log 2>&1 &
nohup python data_server.py >$LOG_DIR/server.log 2>&1 &
nohup python context_cron_task.py >$LOG_DIR/context_cron_task.log 2>&1 &
nohup python conversation_cron_task.py >$LOG_DIR/conversation_cron_task.log 2>&1 &
nohup python scripts/conversation_visualization.py >$LOG_DIR/visual.log 2>&1 &