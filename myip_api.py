import requests

def my_ip():
    try:
        ipv4 = requests.get("https://api.ipify.org").text
        ipv6 = requests.get("https://api64.ipify.org").text
        return {
            "ipv4": ipv4,
            "ipv6": ipv6
        }
    except Exception as e:
        return {"error": str(e)}, 500
