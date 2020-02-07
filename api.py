import json

import redis
import os
from flask import request, jsonify

from .finn import scrape_ad

from .app import app

use_cache = os.getenv("USE_CACHE", False)
if use_cache:
    redis_service = redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"))
    cache_duration = int(os.getenv("CACHE_DURATION_SECONDS", 23 * 60 * 60)) # This could maybe be 2 weeks (duration of ads)

@app.route("/", methods=["GET"])
def ad_detail():
    finnkode = request.args.get("finnkode")
    if not finnkode or not finnkode.isdigit():
        return jsonify(
            **{
                "error": "Missing or invalid param finnkode. Try /?finnkode=KODE"
            }
        )

    cache_key = "finn-ad:{}".format(finnkode)
    ad = False
    if use_cache:
        ad = redis_service.get(cache_key)
    if not ad:
        ad = scrape_ad(finnkode)
        if use_cache:
            redis_service.set(cache_key, json.dumps(ad), cache_duration)
    else:
        app.logger.info("Using Cache")
        ad = json.loads(ad)
    return jsonify(ad=ad)


if __name__ == "__main__":
    app.run(debug=True)
