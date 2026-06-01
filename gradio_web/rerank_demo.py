import requests
import base64

# 读取图片并转为 base64
with open("document.jpg", "rb") as f:
    image_data = base64.b64encode(f.read()).decode()

response = requests.post(
    "http://10.17.150.235:8000/layout-parsing",
    json={"image": image_data}
)

result = response.json()
print(result)