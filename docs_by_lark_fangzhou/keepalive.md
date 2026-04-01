	

## 1.2 最佳实践

1. 系统最初仅支持麦克风输入，现已逐步扩展，支持文本和录音文件作为输入源。具体说明如下：
	1. **麦克风输入**
		1. 采用流式输入输出架构，音频会实时上传，推荐20ms一包发送服务端
			
		2. 客户端无需额外发送静音片段
			
	2. **麦克风（包含静音按键）输入**
		1. 麦克风正常打开时候流式输入，音频实时上传【**强烈推荐**】20ms一包发送服务端
			
		2. 麦克风静音时候无法上传音频到服务端，需要指定如下参数避免音频流超时报错
			
		
		```json
		{
		    "dialog": {
		        "extra": {
		            "input_mod": "keep_alive"
		        }
		    }
		}
		```
		
	3. **麦克风按键输入**
		1. 产品交互形态为按下麦克风按键开始收音，音频实时上传【**强烈推荐****】**20ms一包发送服务端
			
		2. 此模式下无需补充静音，需要指定如下参数即可生效：
			
		
		```json
		{
		    "dialog": {
		        "extra": {
		            "input_mod": "push_to_talk"
		        }
		    }
		}
		```
		
	4. **纯文本输入**
		1. 支持直接以文本形式发起对话。
			
		2. 服务端会自动补充静音片段，保证流式链路的完整性。
			
		
		```json
		{
		    "dialog": {
		        "extra": {
		            "input_mod": "text"
		        }
		    }
		}
		```
		
	5. **录音文件输入**
		1. 支持将录音文件作为输入源，但是需要将录音文件改为流式发送，【**强烈推荐****】**发送20ms的音频包休眠20ms。
			
		2. 对于采样率 16k、位深 int16 的pcm音频而言，20ms 的音频包大小为 640 字节。
			
		3. 服务端同样会自动补充静音片段，保持与麦克风实时流式输入一致的处理逻辑。
			
		
		```json
		{
		    "dialog": {
		        "extra": {
		            "input_mod": "audio_file"
		        }
		    }
		}
		```
		
2. 在客户端发送 FinishSession 事件后，系统将不再返回任何事件。但客户端仍可复用与火山语音网关之间的 WebSocket 连接。若需发起新的会话，客户端需重新从 StartSession 事件开始。
	

![alt](https://portal.volccdn.com/obj/volcfe/cloud-universal-doc/upload_599872d64368dd23fb9dd80e341ce049.png)

3. 在没有对话需求时候，可以发送FinishSession事件结束会话。如果不想复用websocket连接，可以继续发送FinishConnection事件，释放对应的websocket连接。
	
4. 推荐客户端在事件的 optional 字段中携带 event 和 session ID，以降低开发成本，并将事件处理的复杂性交由火山语音服务端负责。
	
5. 客户在集成端到端语音合成模型过程中，使用 ChatTTSText 进行音频合成请求的最佳实践方法，其中黄色部分需要客户实现：
	

![alt](https://portal.volccdn.com/obj/volcfe/cloud-universal-doc/upload_8d8803892a91951007f3abffd3dc8a3c.png)



