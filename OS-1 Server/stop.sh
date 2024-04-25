USER=deploy
#for process in asr_server.py vad_server.py tts_server.py data_server.py chatbot_server.py active_chatbot_server.py image_server.py audio_server.py msg_server.py context_cron_task.py conversation_cron_task.py multiprocessing.resource_tracker multiprocessing.spawn
# for process in data_server.py chatbot_server.py active_chatbot_server.py image_server.py audio_server_v2.py msg_server.py context_cron_task.py conversation_cron_task.py multiprocessing.resource_tracker multiprocessing.spawn embedding_server.py rpn_server.py vicuna-memory LLaVA-7B-v0
for process in data_server.py chatbot_server.py active_chatbot_server.py image_server.py audio_server_v2.py msg_server.py context_cron_task.py conversation_cron_task.py system_monitor.py multiprocessing.resource_tracker multiprocessing.spawn
#for process in chatbot_server.py active_chatbot_server.py
do
  echo $process
  pid=$(ps aux | grep $USER |  grep $process | grep -v grep | awk '{print $2}')
  if [ -n "$pid" ]
  then
      echo "进程已存在，进程ID为$pid，正在杀死进程..."
      if [ $process == "system_monitor.py" ]
      then
        kill $pid
      else
        kill -9 $pid
      fi
  else
      echo "进程不存在"
  fi
done

