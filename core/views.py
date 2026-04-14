from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
import math
from core.models import UserLocation

# 🔥 GLOBAL ACCESS TOKEN CACHE
ACCESS_TOKEN = None


# 📍 DISTANCE FUNCTION
def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371000

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)

    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    return R * c


# 🔥 GET ACCESS TOKEN (ONLY ONCE)
def get_access_token():
    global ACCESS_TOKEN

    if ACCESS_TOKEN:
        return ACCESS_TOKEN

    from google.oauth2 import service_account
    import google.auth.transport.requests

    SERVICE_ACCOUNT_FILE = "service-account.json"
    SCOPES = ["https://www.googleapis.com/auth/firebase.messaging"]

    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )

    request = google.auth.transport.requests.Request()
    credentials.refresh(request)

    ACCESS_TOKEN = credentials.token

    return ACCESS_TOKEN


# 🔔 SEND NOTIFICATION
def send_notification(token, lat, lng):
    import requests

    try:
        access_token = get_access_token()

        url = "https://fcm.googleapis.com/v1/projects/safetyapp-cdb32/messages:send"

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        data = {
            "message": {
                "token": token,
                "notification": {
                    "title": "🚨 Emergency Alert",
                    "body": f"Danger nearby! Location: {lat}, {lng}",
                }
            }
        }

        response = requests.post(url, headers=headers, json=data, timeout=5)

        print("📤 FCM RESPONSE:", response.text)

    except Exception as e:
        print("❌ FCM ERROR:", e)


# 🚨 ALERT API
@csrf_exempt
def alert(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body.decode('utf-8'))

            lat = float(data.get("lat"))
            lng = float(data.get("lng"))
            token = data.get("token")

            if not token:
                return JsonResponse({"status": "error", "message": "Token missing"})

            print("🚨 ALERT:", lat, lng)

            # 🔥 SAFE DB WRITE (NO LOCK CRASH)
            try:
                UserLocation.objects.update_or_create(
                    token=token,
                    defaults={
                        "name": "User",
                        "latitude": lat,
                        "longitude": lng
                    }
                )
            except Exception as e:
                print("❌ DB ERROR:", e)

            # 🔥 FETCH USERS ONCE
            users = list(UserLocation.objects.all())

            nearby_users = []

            for user in users:
                distance = calculate_distance(lat, lng, user.latitude, user.longitude)

                if distance <= 100000:  # 🔥 TEST MODE (100km)
                    nearby_users.append(user)

            print("👥 Nearby Users:", len(nearby_users))

            # 🔥 EXTRACT TOKENS (DB se alag)
            tokens = [
                user.token for user in nearby_users
                if user.token and len(user.token) > 100
            ]

            # 🔔 SEND NOTIFICATION (NO DB LOCK)
            for t in tokens:
                try:
                    send_notification(t, lat, lng)
                except Exception as e:
                    print("❌ NOTIFY ERROR:", e)

            return JsonResponse({
                "status": "ok",
                "nearby_users": len(nearby_users)
            })

        except Exception as e:
            print("❌ MAIN ERROR:", e)
            return JsonResponse({"status": "error"})

    return JsonResponse({"error": "Only POST allowed"})