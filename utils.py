from datetime import datetime
import traceback


def log_message(msg: str, type="FIXME"):
    output_msg = f"[{datetime.now().isoformat()}] {type}: {msg.encode()}"
    print(output_msg)
    with open("./logs/{}.txt".format(datetime.now().isoformat()[:10]), 'a') as log_writer:
        log_writer.write(f"{output_msg}\n")

def log_exception(msg: Exception):
    time_str = "[" + datetime.now().isoformat() + "] {}: ".format(type)
    print("{}{}\n{}\n".format(time_str, repr(msg).encode(), traceback.format_exc()))
    with open("./logs/{}.txt".format(datetime.now().isoformat()[:10]), 'a') as log_writer:
        log_writer.write("{}{}\n".format(time_str, repr(msg).encode()))
    with open("./errors/{}.txt".format(datetime.now().isoformat()[:10]), 'a') as log_writer:
        log_writer.write("{}{}\n{}\n".format(time_str, repr(msg).encode(), traceback.format_exc()))
