import json
import re
import os
from mcap.writer import Writer

# --- CONFIGURATION ---
input_folder = "./raw_logs"
output_folder = "./mcap_logs"
# ---------------------

def candump_to_mcap(input_path, output_path):
    """
    Parses a candump text file and serializes it into an MCAP file.
    """
    with open(output_path, "wb", buffering=1024*1024) as f:
        writer = Writer(f)
        writer.start()

        # Register the JSON schema for CAN messages
        schema_id = writer.register_schema(
            name="can_msg",
            encoding="jsonschema",
            data=json.dumps({
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "data": {"type": "array", "items": {"type": "integer"}},
                    "interface": {"type": "string"}
                }
            }).encode()
        )

        # Register the channel
        channel_id = writer.register_channel(
            topic="/can/raw",
            message_encoding="json",
            schema_id=schema_id,
        )

        # Robust Regex for formats
        line_regex = re.compile(
            r"\((?P<time>\d+\.\d+)\)\s+(?P<iface>\S+)\s+(?P<id>[0-9A-F]+)\s+\[\d+\]\s+(?P<data>.+)",
            re.IGNORECASE
        )

        with open(input_path, "r") as log:
            for line in log:
                match = line_regex.search(line)
                if not match:
                    continue

                groups = match.groupdict()
                
                # Extract bytes and filter hex values
                raw_parts = groups["data"].split()
                byte_data = []
                for part in raw_parts:
                    if len(part) <= 2 and all(c in "0123456789abcdefABCDEF" for c in part):
                        byte_data.append(int(part, 16))

                # Convert seconds to nanoseconds for MCAP
                timestamp_ns = int(float(groups["time"]) * 1e9)
                
                writer.add_message(
                    channel_id=channel_id,
                    log_time=timestamp_ns,
                    publish_time=timestamp_ns,
                    data=json.dumps({
                        "id": int(groups["id"], 16),
                        "data": byte_data,
                        "interface": groups["iface"]
                    }).encode("utf-8")
                )

        writer.finish()

if __name__ == "__main__":

    # Ensure output directory exists
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        print(f"Created output folder: {output_folder}")

    # Ensure input directory exists
    if not os.path.exists(input_folder):
        os.makedirs(input_folder)
        print(f"Created input folder: {input_folder}. Place .txt logs here to process.")
    
    # Process files
    log_files = [f for f in os.listdir(input_folder) if f.endswith((".txt", ".log"))]
    
    if not log_files:
        print("No log files found to process.")
    else:
        for filename in log_files:
            print(f"Processing {filename}...", end="\r")
            in_path = os.path.join(input_folder, filename)
            out_path = os.path.join(output_folder, os.path.splitext(filename)[0] + ".mcap")
            
            try:
                candump_to_mcap(in_path, out_path)
            except Exception as e:
                print(f"\n [ERROR] {filename}: {e}")
        
        print("\nProcess completed successfully.")