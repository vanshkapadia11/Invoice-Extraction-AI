from PIL import Image, ImageDraw
import random
import os


def generate_invoice():
    img = Image.new("RGB", (800, 1000), color="white")
    draw = ImageDraw.Draw(img)

    invoice_no = str(random.randint(10000000, 99999999))
    date = f"{random.randint(1,12):02d}/{random.randint(1,28):02d}/2024"
    amount = random.randint(10000, 99999)
    tax = round(amount * 0.18, 2)
    total = round(amount + tax, 2)

    draw.text((50, 50), "INVOICE", fill="black")
    draw.text((50, 100), f"Invoice No : {invoice_no}", fill="black")
    draw.text((50, 130), f"Date       : {date}", fill="black")
    draw.text((50, 200), "Seller:", fill="black")
    draw.text((50, 230), "Sharma & Associates Pvt Ltd", fill="black")
    draw.text((50, 255), "123 MG Road Mumbai MH 400001", fill="black")
    draw.text((400, 200), "Client:", fill="black")
    draw.text((400, 230), "Rajesh Enterprises", fill="black")
    draw.text((400, 255), "456 FC Road Pune MH 411001", fill="black")
    draw.line([(50, 320), (750, 320)], fill="black", width=1)
    draw.text((50, 340), "Description", fill="black")
    draw.text((500, 340), "Amount", fill="black")
    draw.line([(50, 360), (750, 360)], fill="black", width=1)
    draw.text((50, 380), "Web Development Services", fill="black")
    draw.text((500, 380), f"Rs. {amount}", fill="black")
    draw.line([(50, 420), (750, 420)], fill="black", width=1)
    draw.text((50, 450), f"GST 18% : Rs. {tax}", fill="black")
    draw.text((50, 490), f"Total   : Rs. {total}", fill="black")

    # Save to exact folder
    save_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "test_invoice.png"
    )
    img.save(save_path)

    print(f"Saved to  : {save_path}")
    print(f"Invoice No: {invoice_no}")
    print(f"Date      : {date}")
    print(f"Total     : Rs. {total}")
    print(f"Tax       : Rs. {tax}")


generate_invoice()
