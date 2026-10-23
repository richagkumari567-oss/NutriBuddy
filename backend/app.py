from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from google import genai
import os
import json
import base64

# ---------------------------------------------------------
# Load environment variables
# ---------------------------------------------------------

load_dotenv()

app = Flask(__name__)
CORS(app)

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError(
        "GEMINI_API_KEY not found. Make sure your .env file contains "
        "GEMINI_API_KEY=YOUR_KEY"
    )

client = genai.Client(api_key=api_key)


# ---------------------------------------------------------
# Home route
# ---------------------------------------------------------

@app.route("/")
def home():
    return "NutriBuddy Backend is working! 🍃"


# ---------------------------------------------------------
# Food analysis route
# ---------------------------------------------------------

@app.route("/analyze-food", methods=["POST"])
def analyze_food():

    try:

        # -------------------------------------------------
        # 1. Check image
        # -------------------------------------------------

        if "image" not in request.files:
            return jsonify({
                "success": False,
                "error": "No image received."
            }), 400

        image_file = request.files["image"]

        if image_file.filename == "":
            return jsonify({
                "success": False,
                "error": "No image selected."
            }), 400

        image_bytes = image_file.read()

        if not image_bytes:
            return jsonify({
                "success": False,
                "error": "The uploaded image is empty."
            }), 400

        # -------------------------------------------------
        # 2. Convert image to base64
        # -------------------------------------------------

        image_base64 = base64.b64encode(image_bytes).decode("utf-8")

        mime_type = image_file.mimetype or "image/jpeg"

        # -------------------------------------------------
        # 3. Get food database names from frontend
        # -------------------------------------------------

        database_text = request.form.get("food_database", "[]")

        try:
            database_names = json.loads(database_text)

            if not isinstance(database_names, list):
                database_names = []

        except json.JSONDecodeError:
            database_names = []

        # Remove duplicates and keep only valid strings
        database_names = [
            str(name).strip()
            for name in database_names
            if str(name).strip()
        ]

        allowed_foods = "\n".join(
            f"- {name}" for name in database_names
        )

        if not allowed_foods:
            allowed_foods = "- No database food list was provided."


        # -------------------------------------------------
        # 4. Gemini prompt
        # -------------------------------------------------

        prompt = f"""
You are the food recognition engine for NutriBuddy, an AI nutrition
tracking application.

Analyze the ENTIRE uploaded food image carefully.

IMPORTANT:
This image may contain a complete meal, an Indian thali, a plate
containing several dishes, or a combination of foods.

Your job is to identify EVERY DISTINCT VISIBLE FOOD ITEM.

DO NOT identify only the main dish.

For example, if an Indian thali contains:
- rice
- dal
- roti
- vegetable curry
- curd
- salad

you should return ALL six items separately.

==================================================
FOODS AVAILABLE IN THE NUTRITION DATABASE
==================================================

You MUST choose food names from this list whenever a suitable match exists:

{allowed_foods}

Use the database name EXACTLY as written.

Do NOT invent a new food name when a suitable database food exists.

==================================================
IMPORTANT VISUAL DISTINCTIONS
==================================================

LITTI:
- Usually round or oval baked/roasted wheat balls.
- Often brown with darker roasted spots.
- Commonly served with chokha.
- It is NOT a samosa.

SAMOSA:
- Usually triangular or pyramid-shaped.
- Has a distinct pastry shell.
- Usually contains a potato/vegetable filling.
- It is NOT litti.

ROTI / CHAPATI:
- Flat, round bread.

PARATHA:
- Flat layered bread, usually thicker than roti.

DOSA:
- Thin, large, flat/crispy fermented rice-lentil crepe.

MASALA DOSA:
- Dosa containing visible potato masala/filling.

IDLI:
- Small, round, soft steamed cakes.

VADA:
- Fried, round/doughnut-like or irregular fritter.

RICE:
- Loose cooked rice grains.

POHA:
- Flattened rice flakes, usually loose and mixed with vegetables/
  peanuts/spices.

DAL:
- Liquid or semi-liquid lentil preparation.

CHOKHA:
- Mashed vegetable preparation, commonly potato, brinjal, or tomato,
  often served with litti.

ICE CREAM:
- Look carefully for ice cream scoops, cones, cups, bars, sandwiches,
  or clearly recognizable packaged ice-cream products.
- A branded/wrapped ice-cream product should still be counted as
  "Ice Cream" when the visible product is clearly ice cream.
- Do not confuse a small Indian sweet with ice cream.

NAMKEEN / SEV / BHUJIA:
- Namkeen is a savory Indian snack, often appearing as a loose pile of
  thin fried noodles, sev, bhujia, boondi, peanuts, or mixed crunchy
  snack pieces.
- If a clearly visible loose orange/yellow/brown savory snack pile is
  present, consider "Namkeen" or "Sev / Bhujia" instead of ignoring it.
- Also count namkeen when it is visible inside a packet/container.

PANEER:
- Visible paneer pieces/cheese cubes.

PANEER CURRY:
- Paneer pieces in a visible gravy/curry.

==================================================
MULTI-ITEM / THALI RULE
==================================================

If several foods are visibly separate, return them as separate items.

Do not ignore small side portions because one food dominates the image.
Inspect every plate compartment, bowl, corner, packet, cone, cup, and
small snack pile for additional visible food items.

For example:

A thali containing rice + dal + roti + sabzi + curd:

[
  {{"name":"Rice (White)","unit":"cup","qty":1}},
  {{"name":"Dal","unit":"bowl","qty":0.5}},
  {{"name":"Roti","unit":"piece","qty":2}},
  {{"name":"Mixed Vegetables","unit":"cup","qty":0.75}},
  {{"name":"Curd","unit":"cup","qty":0.5}}
]

For Litti Chokha:

If Litti and Chokha are visibly separate, prefer:

[
  {{"name":"Litti","unit":"piece","qty":4}},
  {{"name":"Chokha","unit":"cup","qty":1}}
]

Only use "Litti Chokha" when the image is best represented as one
combined serving and the separate quantities cannot reasonably be
estimated.

==================================================
QUANTITY ESTIMATION
==================================================

Estimate the visible portion as realistically as possible.

Use:
- piece for individual items
- cup for foods such as rice, vegetables, poha or chokha
- bowl for dal, curry or similar dishes
- serving when a combined serving is more appropriate
- large / medium / small when appropriate

Examples:
2 rotis -> qty 2
4 litti -> qty 4
half cup rice -> qty 0.5
one bowl dal -> qty 1

Do not return random quantities.

==================================================
IMPORTANT SAFETY / ACCURACY RULES
==================================================

Only return foods that are actually visible.

Do not guess hidden foods.

Do not calculate calories.

Do not calculate protein.

Do not calculate carbohydrates.

Do not calculate fat.

Nutrition values will be calculated separately by NutriBuddy's
database.

If a visible food does not have a suitable database match, use the
closest appropriate database food ONLY if the match is reasonable.
Otherwise omit that item rather than inventing a food name.

==================================================
OUTPUT FORMAT
==================================================

Return ONLY a valid JSON array.

No markdown.
No ```json.
No explanation.

Each object MUST contain exactly:

name
unit
qty
confidence

confidence must be an integer from 0 to 100 representing how confident
you are that the visible item is correctly identified as that food.
Use lower confidence when the food is partially hidden, blurry, small,
ambiguous, or visually similar to another database food.

Example:

[
  {{"name":"Rice (White)","unit":"cup","qty":1,"confidence":94}},
  {{"name":"Dal","unit":"bowl","qty":0.5,"confidence":82}},
  {{"name":"Roti","unit":"piece","qty":2,"confidence":96}}
]
"""


        # -------------------------------------------------
        # 5. Send image + prompt to Gemini
        # -------------------------------------------------

        interaction = client.interactions.create(
            model="gemini-3.6-flash",
            input=[
                {
                    "type": "text",
                    "text": prompt
                },
                {
                    "type": "image",
                    "data": image_base64,
                    "mime_type": mime_type
                }
            ]
        )


        # -------------------------------------------------
        # 6. Read Gemini response
        # -------------------------------------------------

        result = interaction.output_text.strip()

        print("\n========== GEMINI RAW RESPONSE ==========")
        print(result)
        print("=========================================\n")


        # Remove accidental markdown fences
        result = result.replace("```json", "")
        result = result.replace("```", "")
        result = result.strip()


        # -------------------------------------------------
        # 7. Convert response to JSON
        # -------------------------------------------------

        try:

            food_items = json.loads(result)

        except json.JSONDecodeError:

            # Try to recover a JSON array if Gemini added text
            start = result.find("[")
            end = result.rfind("]")

            if start != -1 and end != -1 and end > start:

                possible_json = result[start:end + 1]

                food_items = json.loads(possible_json)

            else:
                raise


        # -------------------------------------------------
        # 8. Validate response
        # -------------------------------------------------

        if not isinstance(food_items, list):

            return jsonify({
                "success": False,
                "error": "Gemini returned an invalid food list."
            }), 500


        cleaned_items = []


        for item in food_items:

            if not isinstance(item, dict):
                continue

            name = item.get("name")
            unit = item.get("unit", "serving")
            qty = item.get("qty", 1)
            confidence = item.get("confidence", 70)

            if not name:
                continue

            try:
                confidence = int(float(confidence))
            except (ValueError, TypeError):
                confidence = 70

            confidence = max(0, min(100, confidence))


            # Convert quantity to a number
            try:
                qty = float(qty)

            except (ValueError, TypeError):
                qty = 1


            # Prevent invalid quantities
            if qty <= 0:
                qty = 1


            # -------------------------------------------------
            # Ensure Gemini selected a database food
            # -------------------------------------------------
            selected_name = str(name).strip()

            exact_match = None

            for db_name in database_names:

                if db_name.lower().strip() == selected_name.lower():

                    exact_match = db_name
                    break


            if exact_match:

                selected_name = exact_match

            else:

                # Case-insensitive partial fallback
                # This helps with small naming differences.
                partial_match = None

                selected_lower = selected_name.lower()

                for db_name in database_names:

                    db_lower = db_name.lower()

                    if (
                        selected_lower in db_lower
                        or db_lower in selected_lower
                    ):
                        partial_match = db_name
                        break

                if partial_match:
                    selected_name = partial_match

                else:
                    print(
                        "Skipping food not found in database:",
                        selected_name
                    )
                    continue


            cleaned_items.append({
                "name": selected_name,
                "unit": str(unit),
                "qty": qty,
                "confidence": confidence
            })


        # -------------------------------------------------
        # 9. Check whether anything was detected
        # -------------------------------------------------

        if len(cleaned_items) == 0:

            return jsonify({
                "success": False,
                "error": (
                    "No recognizable foods from the nutrition "
                    "database were detected."
                )
            }), 200


        # -------------------------------------------------
        # 10. Send result to frontend
        # -------------------------------------------------

        print("\nDetected foods:")
        for food in cleaned_items:
            print(food)

        return jsonify({
            "success": True,
            "foods": cleaned_items
        })


    # -----------------------------------------------------
    # JSON error
    # -----------------------------------------------------

    except json.JSONDecodeError as e:

        print("\nJSON ERROR:")
        print(e)

        return jsonify({
            "success": False,
            "error": "Gemini returned invalid JSON."
        }), 500


    # -----------------------------------------------------
    # General error
    # -----------------------------------------------------

    except Exception as e:

        print("\nBACKEND ERROR:")
        print(e)

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ---------------------------------------------------------
# Start Flask server
# ---------------------------------------------------------

if __name__ == "__main__":

    print("\n======================================")
    print("       NutriBuddy Backend")
    print("======================================")
    print("Server: http://127.0.0.1:5000")
    print("Status: Running")
    print("======================================\n")

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )
