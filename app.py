import streamlit as st
import json
import os
from datetime import datetime, date, timedelta
from PIL import Image

# Optional: Google Gemini AI for automatic photo reading
try:
    from google import genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

# ==========================================
# 1. CONFIGURATION & RULEBOOK DICTIONARY
# ==========================================
st.set_page_config(page_title="SmartShelf AI", page_icon="📦", layout="wide")

DATA_FILE = "smartshelf_data.json"
IMAGE_DIR = "saved_images"
os.makedirs(IMAGE_DIR, exist_ok=True)

# Python Dictionary Rulebook: How many days an item is safe AFTER breaking the seal
OPENED_SHELF_LIFE_RULES = {
    "Medicine - Tablets/Capsules": None,  # Uses normal printed expiry date
    "Medicine - Eye/Ear Drops": 30,       # Expires 30 days after opening!
    "Medicine - Liquid Syrup": 45,        # Expires 45 days after opening!
    "Kitchen - Spices & Dry Goods": 180,  # 6 months after opening
    "Kitchen - Sauces & Dairy": 30,       # 30 days after opening
    "Salon / Cosmetics / Creams": 180,    # 6 months after opening
    "Commercial - Packaged Snacks": None, # Uses normal printed expiry date
    "Other / General": 90
}

# ==========================================
# 2. SIMPLE FILE DATABASE FUNCTIONS
# ==========================================
def load_data():
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []

def save_data(items):
    with open(DATA_FILE, "w") as f:
        json.dump(items, f, indent=4)

def generate_next_tag_id(items):
    if not items:
        return "#101"
    max_num = 100
    for item in items:
        try:
            num = int(item.get("tag_id", "#100").replace("#", ""))
            if num > max_num:
                max_num = num
        except ValueError:
            pass
    return f"#{max_num + 1}"

# ==========================================
# 3. AI CAMERA OCR FUNCTION (WITH FALLBACK)
# ==========================================
def analyze_image_with_ai(image_file, api_key):
    """Sends photo to Gemini Vision AI to auto-extract Name, Category, Expiry, and MRP."""
    if not api_key or not GEMINI_AVAILABLE:
        # Smart fallback for offline college lab demo
        return {
            "name": "Paracetamol 650mg Strip (Auto-Detected)",
            "category": "Medicine - Tablets/Capsules",
            "expiry_date": (date.today() + timedelta(days=20)).strftime("%Y-%m-%d"),
            "mrp": 35.0,
            "note": "Fever & Body Pain - Keep in Bedroom Red Box"
        }

    try:
        client = genai.Client(api_key=api_key)
        img = Image.open(image_file)
        prompt = """
        Look at this product package photo. Extract these details and return ONLY a valid JSON object:
        {
            "name": "Brand and product name",
            "category": "Pick closest from: Medicine - Tablets/Capsules, Medicine - Eye/Ear Drops, Medicine - Liquid Syrup, Kitchen - Spices & Dry Goods, Kitchen - Sauces & Dairy, Salon / Cosmetics / Creams, Commercial - Packaged Snacks, Other / General",
            "expiry_date": "YYYY-MM-DD (estimate if only month/year shown, e.g. 2027-05-01)",
            "mrp": 50.0,
            "note": "Short description of package look (e.g., Blue foil strip) or usage"
        }
        """
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[img, prompt]
        )
        raw_text = response.text.strip().replace("```json", "").replace("```", "").strip()
        return json.loads(raw_text)
    except Exception as e:
        st.warning(f"AI OCR note: Using smart default values ({e})")
        return {
            "name": "Scanned Product Packet",
            "category": "Other / General",
            "expiry_date": (date.today() + timedelta(days=25)).strftime("%Y-%m-%d"),
            "mrp": 100.0,
            "note": "Scanned via SmartShelf Camera"
        }

# ==========================================
# 4. CORE DATE & DISCOUNT LOGIC
# ==========================================
def calculate_days_left(expiry_str):
    exp_date = datetime.strptime(expiry_str, "%Y-%m-%d").date()
    return (exp_date - date.today()).days

def calculate_commercial_discount(days_left, cp, sp, mp):
    """Calculates safe discount on Market Price (MP) without dropping below Cost Price (CP)."""
    if mp <= 0:
        return 0, sp, 0, "Invalid Price"

    # Suggest discount tier based on days left
    if days_left <= 0:
        suggested_disc_pct = 50
    elif days_left <= 7:
        suggested_disc_pct = 25  # 1 Week left
    elif days_left <= 15:
        suggested_disc_pct = 15  # 2 Weeks left
    elif days_left <= 30:
        suggested_disc_pct = 10  # 1 Month left
    else:
        suggested_disc_pct = 0   # Safe zone

    # Calculate discounted price from Market Price (MP)
    raw_discounted_price = mp * (1 - (suggested_disc_pct / 100.0))

    # PROFIT PROTECTION FLOOR: Never let automatic price drop below Cost Price (CP)
    if raw_discounted_price < cp and days_left > 0:
        final_price = cp
        actual_disc_pct = round(((mp - cp) / mp) * 100, 1)
        status = "Protected at Cost Price Floor (Zero Loss!)"
    else:
        final_price = round(raw_discounted_price, 2)
        actual_disc_pct = suggested_disc_pct
        status = "Safe Profit Zone" if final_price > cp else "Break-Even Clearance"

    profit_per_unit = round(final_price - cp, 2)
    return actual_disc_pct, final_price, profit_per_unit, status

# ==========================================
# 5. SIDEBAR: SETTINGS & 1-CLICK DEMO DATA
# ==========================================
st.sidebar.title("⚙️ SmartShelf AI Controls")
app_mode = st.sidebar.radio(
    "Select Operating Mode:",
    ["🏠 Personal & Home Mode", "🏪 Commercial & Godown Mode"]
)

st.sidebar.markdown("---")
st.sidebar.subheader("🤖 Optional AI Camera Key")
api_key = st.sidebar.text_input("Gemini API Key (Leave blank for Demo Mode):", type="password")

st.sidebar.markdown("---")
st.sidebar.subheader("🎓 Viva Demo Helper")
if st.sidebar.button("🚀 Load Sample Viva Items"):
    today = date.today()
    sample_items = [
        {
            "tag_id": "#101",
            "mode": "Personal",
            "name": "Dolo 650 (Paracetamol Strip)",
            "category": "Medicine - Tablets/Capsules",
            "location": "Bedroom Red Medicine Box",
            "visual_note": "Blue & silver foil strip, half cut (6 tablets left). For Fever & Body Pain.",
            "expiry_date": (today + timedelta(days=12)).strftime("%Y-%m-%d"),
            "is_opened": False,
            "status": "Active",
            "image_path": ""
        },
        {
            "tag_id": "#102",
            "mode": "Personal",
            "name": "Mahaflox Eye Drops (10ml)",
            "category": "Medicine - Eye/Ear Drops",
            "location": "Fridge Top Door",
            "visual_note": "Small white dropper bottle. Outer box thrown away.",
            "expiry_date": (today + timedelta(days=400)).strftime("%Y-%m-%d"),
            "is_opened": False,
            "status": "Active",
            "image_path": ""
        },
        {
            "tag_id": "#103",
            "mode": "Commercial",
            "name": "Kurkure Masala Munch (Master Carton - 100 Packs)",
            "category": "Commercial - Packaged Snacks",
            "location": "Godown Rack B2 (Batch #K99)",
            "visual_note": "Brown corrugated carton, Batch #K99 stamped on side",
            "expiry_date": (today + timedelta(days=24)).strftime("%Y-%m-%d"),
            "cp": 15.0,
            "sp": 18.0,
            "mp": 20.0,
            "alert_days": 30,
            "is_opened": False,
            "status": "Active",
            "image_path": ""
        },
        {
            "tag_id": "#104",
            "mode": "Commercial",
            "name": "VLCC Gold Facial Kit (Salon Use / Retail)",
            "category": "Salon / Cosmetics / Creams",
            "location": "Barber Shop Counter Shelf 1",
            "visual_note": "Gold cardboard box - DO NOT use on customer face if expired!",
            "expiry_date": (today + timedelta(days=6)).strftime("%Y-%m-%d"),
            "cp": 140.0,
            "sp": 190.0,
            "mp": 200.0,
            "alert_days": 30,
            "is_opened": False,
            "status": "Active",
            "image_path": ""
        }
    ]
    save_data(sample_items)
    st.sidebar.success("Loaded 4 realistic demo items! Check the dashboard.")
    st.rerun()

if st.sidebar.button("🗑️ Clear All Data"):
    save_data([])
    st.sidebar.info("All items cleared.")
    st.rerun()

# Load existing items
items = load_data()

# ==========================================
# 6. MAIN HEADER & MORNING DIGEST BANNER
# ==========================================
st.title("📦 SmartShelf AI — Visual Expiry & Profit Protection System")
st.caption("Zero daily sales typing. Capture once, protect health at home, and prevent financial loss in shops.")

# Morning Digest Summary
active_items = [i for i in items if i.get("status") == "Active"]
expiring_soon = [i for i in active_items if calculate_days_left(i["expiry_date"]) <= 30]

if expiring_soon:
    st.warning(
        f"🌅 **Smart Morning Digest:** You have **{len(expiring_soon)} item(s)** expiring within 30 days! "
        f"Review the highlighted cards below to mark 'Already Sold Out', break seals, or generate a discount offer."
    )
else:
    st.success("✅ **Smart Morning Digest:** All stored items are safe and well within their expiry dates!")

# ==========================================
# 7. STEP 1: ADD NEW ITEM (CAMERA / AI AUTO-FILL)
# ==========================================
with st.expander("➕ Click Here to Scan / Add a New Item (Camera or Photo Upload)", expanded=False):
    col_cam, col_form = st.columns([1, 1.5])

    with col_cam:
        st.subheader("1. Snap or Upload Photo")
        img_input = st.camera_input("Take Photo of Front/Expiry Stamp")
        upload_input = st.file_uploader("Or Upload Product Photo", type=["jpg", "jpeg", "png"])
        chosen_img = img_input or upload_input

        if chosen_img and st.button("✨ Auto-Read Photo with AI"):
            with st.spinner("AI is reading package label and expiry date..."):
                ai_result = analyze_image_with_ai(chosen_img, api_key)
                st.session_state["auto_name"] = ai_result.get("name", "")
                st.session_state["auto_cat"] = ai_result.get("category", "Other / General")
                st.session_state["auto_exp"] = ai_result.get("expiry_date", (date.today() + timedelta(days=30)).strftime("%Y-%m-%d"))
                st.session_state["auto_mrp"] = float(ai_result.get("mrp", 100.0))
                st.session_state["auto_note"] = ai_result.get("note", "")
                st.success("AI Auto-Filled the form! Verify and click Save.")

    with col_form:
        next_tag = generate_next_tag_id(items)
        st.subheader(f"2. Confirm Details (Write Marker ID `{next_tag}` on item)")

        default_name = st.session_state.get("auto_name", "")
        default_note = st.session_state.get("auto_note", "")
        default_mrp = st.session_state.get("auto_mrp", 100.0)

        item_name = st.text_input("Product Name:", value=default_name, placeholder="e.g., Dolo 650 Strip or Kurkure Carton")
        
        cat_list = list(OPENED_SHELF_LIFE_RULES.keys())
        default_cat_idx = cat_list.index(st.session_state["auto_cat"]) if st.session_state.get("auto_cat") in cat_list else 0
        category = st.selectbox("Category (Controls 'Seal Broken' Expiry Rule):", cat_list, index=default_cat_idx)

        storage_loc = st.text_input("Where is it stored? (Location / Batch #):", placeholder="e.g., Bedroom Box or Godown Rack A2")
        visual_note = st.text_input("Visual Look / Purpose Note:", value=default_note, placeholder="e.g., Blue foil strip - For Fever")

        exp_date_val = st.date_input("Printed Expiry Date:", value=date.today() + timedelta(days=30))

        # Extra fields only for Commercial Mode
        if "Commercial" in app_mode:
            st.markdown("**💰 Commercial Pricing (For No-Loss Discounting):**")
            c1, c2, c3 = st.columns(3)
            cp_val = c1.number_input("Cost Price - CP (₹):", min_value=0.0, value=round(default_mrp * 0.7, 1))
            sp_val = c2.number_input("Selling Price - SP (₹):", min_value=0.0, value=round(default_mrp * 0.9, 1))
            mp_val = c3.number_input("Market Price - MP/MRP (₹):", min_value=0.0, value=default_mrp)
            alert_window = st.selectbox("Notify me before expiry:", [30, 15, 7], format_func=lambda x: f"{x} Days Before Expiry")
        else:
            cp_val, sp_val, mp_val, alert_window = 0.0, 0.0, 0.0, 30

        if st.button("💾 Save Item to SmartShelf", type="primary"):
            if not item_name:
                st.error("Please enter a Product Name.")
            else:
                saved_img_path = ""
                if chosen_img:
                    saved_img_path = os.path.join(IMAGE_DIR, f"{next_tag.replace('#', 'item_')}.jpg")
                    Image.open(chosen_img).convert("RGB").save(saved_img_path)

                new_item = {
                    "tag_id": next_tag,
                    "mode": "Commercial" if "Commercial" in app_mode else "Personal",
                    "name": item_name,
                    "category": category,
                    "location": storage_loc or "General Storage",
                    "visual_note": visual_note or "No visual note added",
                    "expiry_date": exp_date_val.strftime("%Y-%m-%d"),
                    "cp": cp_val,
                    "sp": sp_val,
                    "mp": mp_val,
                    "alert_days": alert_window,
                    "is_opened": False,
                    "status": "Active",
                    "image_path": saved_img_path
                }
                items.append(new_item)
                save_data(items)
                st.success(f"Saved! Tip: Write `{next_tag}` on the packet with a marker so you can always identify it.")
                st.rerun()

st.markdown("---")

# ==========================================
# 8. STEP 2: SEARCH & LIVE INVENTORY CARDS
# ==========================================
mode_filter = "Commercial" if "Commercial" in app_mode else "Personal"
st.subheader(f"🔍 Your {mode_filter} Inventory & Expiry Radar")

search_query = st.text_input("Search by Name, Symptom (e.g., 'Fever'), Marker ID (#101), or Location:", "")

filtered_items = [
    i for i in items
    if i.get("status") == "Active"
    and i.get("mode") == mode_filter
    and (
        search_query.lower() in i.get("name", "").lower()
        or search_query.lower() in i.get("visual_note", "").lower()
        or search_query.lower() in i.get("tag_id", "").lower()
        or search_query.lower() in i.get("location", "").lower()
    )
]

if not filtered_items:
    st.info(f"No active items in {mode_filter} Mode yet. Click **'🚀 Load Sample Viva Items'** in the left sidebar to test immediately!")

for idx, item in enumerate(filtered_items):
    days_left = calculate_days_left(item["expiry_date"])

    # Determine status color badge
    if days_left < 0:
        badge = f"🚨 EXPIRED ({abs(days_left)} days ago) — THROW IN TRASH / DO NOT USE!"
        border_color = "🔴"
    elif days_left <= 7:
        badge = f"🔥 CRITICAL: Only {days_left} days left!"
        border_color = "🟠"
    elif days_left <= 30:
        badge = f"⚠️ EXPIRING SOON: {days_left} days left"
        border_color = "🟡"
    else:
        badge = f"✅ SAFE: {days_left} days remaining"
        border_color = "🟢"

    with st.container(border=True):
        c_left, c_mid, c_right = st.columns([1, 2.2, 1.8])

        # COLUMN 1: Visual Identification & Marker Tag
        with c_left:
            st.markdown(f"### {border_color} `{item['tag_id']}`")
            st.caption("Write this ID on the packet")
            if item.get("image_path") and os.path.exists(item["image_path"]):
                st.image(item["image_path"], use_container_width=True)
            else:
                st.info("📷 Visual Note:\n\n" + item.get("visual_note", "Standard package"))

        # COLUMN 2: Core Details & "Seal Broken" Logic
        with c_mid:
            st.markdown(f"### {item['name']}")
            st.markdown(f"**Status:** {badge}")
            st.write(f"📂 **Category:** {item['category']} | 📍 **Location:** `{item['location']}`")
            st.write(f"🗓️ **Effective Expiry Date:** `{item['expiry_date']}`")

            # Show "Opened / Seal Broken" rule if applicable
            rule_days = OPENED_SHELF_LIFE_RULES.get(item["category"])
            if rule_days:
                if item.get("is_opened"):
                    st.info(f"🔓 **Seal Broken Active:** Expiry was automatically adjusted to {rule_days} days from opening.")
                else:
                    if st.button(f"🔓 Just Opened / Break Seal (Resets to {rule_days} Days)", key=f"open_{item['tag_id']}"):
                        new_exp = date.today() + timedelta(days=rule_days)
                        current_exp = datetime.strptime(item["expiry_date"], "%Y-%m-%d").date()
                        # Take whichever date comes sooner!
                        final_exp = min(new_exp, current_exp)
                        item["expiry_date"] = final_exp.strftime("%Y-%m-%d")
                        item["is_opened"] = True
                        save_data(items)
                        st.rerun()

        # COLUMN 3: Actions (Personal vs Commercial)
        with c_right:
            if mode_filter == "Personal":
                st.markdown("#### 🏠 Home Actions")
                st.write(f"📝 **Purpose / Look:** {item['visual_note']}")
                if st.button("✅ Used Up / Thrown in Trash", key=f"done_{item['tag_id']}", use_container_width=True):
                    item["status"] = "Completed"
                    save_data(items)
                    st.rerun()

            else:
                st.markdown("#### 🏪 Shopkeeper Profit Shield")
                cp, sp, mp = item.get("cp", 0), item.get("sp", 0), item.get("mp", 0)
                st.write(f"**CP:** ₹{cp} | **Normal SP:** ₹{sp} | **MRP (MP):** ₹{mp}")

                disc_pct, new_price, profit, status_msg = calculate_commercial_discount(days_left, cp, sp, mp)

                # Allow shopkeeper to adjust discount manually with a slider
                custom_disc = st.slider(
                    "Adjust Discount % on MP:",
                    min_value=0, max_value=50, value=int(disc_pct),
                    key=f"slider_{item['tag_id']}"
                )
                manual_price = round(mp * (1 - custom_disc / 100.0), 2)
                manual_profit = round(manual_price - cp, 2)

                if manual_price < cp:
                    st.error(f"⚠️ Price ₹{manual_price} is BELOW Cost Price (₹{cp})! Loss of ₹{abs(manual_profit)}/unit.")
                else:
                    st.success(f"🏷️ **Offer Price: ₹{manual_price}** ({custom_disc}% off MP) | **Profit: +₹{manual_profit}/unit**")

                # 1-Click Sold Out Button (Zero daily typing!)
                if st.button("🎉 1-Click: Already Sold Out!", key=f"sold_{item['tag_id']}", type="primary", use_container_width=True):
                    item["status"] = "Sold Out"
                    save_data(items)
                    st.rerun()

                # 1-Click WhatsApp Offer Generator
                with st.popover("📢 Generate WhatsApp Deal Card", use_container_width=True):
                    wa_text = (
                        f"🔥 *SUPER SAVER FLASH DEAL!* 🔥\n"
                        f"🛍️ *Item:* {item['name']}\n"
                        f"❌ *MRP:* ~₹{mp}~\n"
                        f"✅ *Today's Offer Price:* *₹{manual_price}* ({custom_disc}% OFF!)\n"
                        f"📍 *Available Now! Hurry before stock finishes!*"
                    )
                    st.text_area("Copy & Paste to WhatsApp Status / Group:", value=wa_text, height=130, key=f"wa_{item['tag_id']}")
