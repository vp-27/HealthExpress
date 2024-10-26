from datetime import datetime
import logging
import re
from flask import (
    Flask,
    redirect,
    request,
    render_template,
    jsonify,
    Response,
    stream_with_context,
    session,
    url_for,
)
from twilio.twiml.voice_response import VoiceResponse, Gather
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
from dotenv import load_dotenv
import os
import time
from flask_cors import CORS
from tts import text_to_speech
import json
from user_history import finalize_call, load_user_history, save_user_history
from conversation_logic import (
    generate_openai_response,
    interpret_response,
    update_user_history,
    rephrase_question,
)
from tree import decisionTree

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")
CORS(app)

# Load environment variables
load_dotenv()

# Twilio and OpenAI credentials
account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
openai_api_key = os.getenv("OPENAI_API_KEY")
twilio_phone_number = os.getenv("TWILIO_PHONE_NUMBER")
ngrok_url = os.getenv("NGROK_URL")
print("ngrok_url: ", ngrok_url)
print("eleven_api_key: ", os.getenv("ELEVEN_API_KEY"))
# Twilio client
client = Client(account_sid, auth_token)

# Global variables
predictionState = "root"
conversation_history = {}

language_mappings = {
    "en": {
        "welcome": "Hello, welcome to the AI-assisted medical diagnosis.",
        "welcome_back": "Hello {}, welcome back to the AI-assisted medical diagnosis.",
        "didnt_catch": "I'm sorry, I didn't catch that. Could you please repeat?",
        "couldnt_understand": "I couldn't understand your response.",
        "consult_professional": "Based on your answers, you may have {}. Please consult a medical professional for proper diagnosis.",
        "thank_you": "Thank you for your time. Goodbye!",
        "error_processing": "I'm sorry, I'm having trouble processing your response. Let's try again.",
        "error_occurred": "I'm sorry, an error occurred. Please try again later.",
        "gather_language": "en-US",
    },
    "hi": {
        "welcome": "नमस्ते, AI-सहायता प्राप्त चिकित्सा निदान में आपका स्वागत है।",
        "welcome_back": "नमस्ते {}, AI-सहायता प्राप्त चिकित्सा निदान में आपका फिर से स्वागत है।",
        "didnt_catch": "क्षमा करें, मुझे वह समझ नहीं आया। कृपया दोहराएं?",
        "couldnt_understand": "मैं आपके जवाब को समझ नहीं पाया।",
        "consult_professional": "आपके जवाबों के आधार पर, आपको {} हो सकता है। कृपया उचित निदान के लिए चिकित्सा पेशेवर से परामर्श करें।",
        "thank_you": "आपके समय के लिए धन्यवाद। अलविदा!",
        "error_processing": "क्षमा करें, मुझे आपके जवाब को संसाधित करने में समस्या हो रही है। फिर से प्रयास करें।",
        "error_occurred": "क्षमा करें, एक त्रुटि हुई। कृपया बाद में पुनः प्रयास करें।",
        "gather_language": "hi-IN",
    },
    "ta": {
        "welcome": "வணக்க��், AI உதவியாளர் மருத்துவக் கண்டறிதலில் உங்களை வரவேற்கிறது.",
        "welcome_back": "வணக்கம் {}, AI உதவியாளர் மருத்துவக் கண்டறிதலில் உங்களை மீண்டும் வரவேற்கிறது.",
        "didnt_catch": "மன்னிக்கவும், எனக்குப் புரியவில்லை. தயவுசெய்து மறுபடியும் சொல்க!",
        "couldnt_understand": "உங்கள் பதில் எனக்குப் புரியவில்லை.",
        "consult_professional": "உங்கள் பதில்களின் அடிப்படையில், உங்களுக்கு {} இருக்கலாம். சரியான கண்டறிதலுக்காக ஒரு மருத்துவ நிபுணரின் ஆலோசனைப் பெறவும்.",
        "thank_you": "உங்கள் நேரத்திற்காக நன்றி. விடை!",
        "error_processing": "மன்னிக்கவும், உங்கள் பதிலைப் புரிந்துகொள்வ��ில் சிரமமாகிறது. மீண்டும் முயற்சிப்போம்.",
        "error_occurred": "மன்னிக்கவும், ஒரு பிழை ஏற்பட்டது. பின்னர் மீண்டும் முயற்சிக்கவும்.",
        "gather_language": "ta-IN",
    },
}


@app.route("/get_conversation", methods=["GET"])
def get_conversation():
    global conversation_history
    call_sid = request.args.get("call_sid")
    if call_sid in conversation_history:
        return jsonify(conversation_history[call_sid])
    return jsonify([])


@app.route("/", methods=["GET", "POST"])
def index():
    return render_template("index.html")


@app.route("/webform")
def webform():
    return render_template("webform.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    language = session.get("language", "en")
    global predictionState, conversation_history
    if request.method == "POST":
        to_number = request.form["to_number"]
        to_number = "".join(filter(str.isdigit, to_number))

        if len(to_number) == 10:
            to_number = f"+1{to_number}"

        if not to_number.startswith("+") or not to_number[1:].isdigit():
            return "Invalid phone number format. Please use E.164 format.", 400

        contact_method = request.form.get(
            "contact_method", "call"
        )  # Default to 'call' if not provided

        try:
            user_history = load_user_history(to_number)

            if contact_method == "call":
                twiml = VoiceResponse()
                predictionState = "root"
                root_question = decisionTree["root"]["question"]

                if user_history["fname"]:
                    speech_text = (
                        language_mappings[language]["welcome_back"].format(
                            user_history["fname"]
                        )
                        + " "
                        + root_question
                    )
                else:
                    speech_text = (
                        language_mappings[language]["welcome"] + " " + root_question
                    )

                # Generate speech file and get S3 URL
                s3_url = text_to_speech(speech_text, language)
                if s3_url:
                    print(f"Audio data URL: {s3_url[:100]}...")
                    twiml.play(s3_url)
                else:
                    twiml.say(
                        "I'm sorry, I couldn't generate the audio. Let's try again."
                    )

                gather = Gather(
                    input="speech",
                    language=language_mappings[language]["gather_language"],
                    action=f"{ngrok_url}/handle_input?language={language}",
                    method="POST",
                    speechTimeout=1,
                    timeout=8,
                )
                twiml.append(gather)

                call = client.calls.create(
                    twiml=str(twiml),
                    to=to_number,
                    from_=twilio_phone_number,
                    status_callback=f"{ngrok_url}/call_status",
                    status_callback_event=[
                        "completed",
                        "busy",
                        "no-answer",
                        "failed",
                        "canceled",
                    ],
                )

                # Add the first message to conversation history
                if call.sid not in conversation_history:
                    conversation_history[call.sid] = []
                conversation_history[call.sid].append(
                    {"speaker": "ai", "text": speech_text}
                )

                logger.info(f"Initiating call to {to_number}. Call SID: {call.sid}")
                return render_template(
                    "call-progress.html", call_sid=call.sid, to_number=to_number
                )
            elif contact_method == "text":
                logger.info(f"Initiating text conversation with {to_number}")

                # Send initial text message
                message = client.messages.create(
                    body=language_mappings[language]["welcome"],
                    from_=twilio_phone_number,
                    to=to_number,
                )

                # Add the first message to conversation history
                if message.sid not in conversation_history:
                    conversation_history[message.sid] = []
                conversation_history[message.sid].append(
                    {"speaker": "ai", "text": language_mappings[language]["welcome"]}
                )

                logger.info(
                    f"Initiating text conversation with {to_number}. Message SID: {message.sid}"
                )
                return render_template(
                    "text-conversation.html",
                    message_sid=message.sid,
                    to_number=to_number,
                )
        except Exception as e:
            logger.error(f"Failed to initiate contact: {str(e)}")
            return f"Failed to initiate contact: {str(e)}", 500

    return render_template("login.html")


@app.route("/sms", methods=["POST"])
def handle_sms():
    language = session.get("language", "en")
    global predictionState, conversation_history

    incoming_msg = request.values.get("Body", "").lower()
    from_number = request.values.get("From", "")

    user_history = load_user_history(from_number)

    # Process the incoming message using the same conversation logic
    try:
        current_node = decisionTree[predictionState]
        current_question = current_node["question"]
        interpreted_response = interpret_response(incoming_msg, current_node)

        new_user_history = update_user_history(
            current_question, incoming_msg, user_history
        )

        if interpreted_response == "invalid":
            ai_response = rephrase_question(
                current_question, incoming_msg, True, new_user_history
            )
        else:
            if interpreted_response in current_node:
                predictionState = current_node[interpreted_response]
            else:
                ai_response = f"{language_mappings[language]['couldnt_understand']} {current_question}"

            if predictionState not in decisionTree:
                ai_response = language_mappings[language][
                    "consult_professional"
                ].format(predictionState)
                finalize_call(user_history)
            else:
                next_question = decisionTree[predictionState]["question"]
                ai_response = rephrase_question(
                    next_question, incoming_msg, False, user_history
                )

        save_user_history(from_number, user_history)

        # Send the response back via SMS
        resp = MessagingResponse()
        resp.message(ai_response)

        return str(resp)

    except Exception as e:
        logger.error(f"Error processing SMS: {str(e)}")
        resp = MessagingResponse()
        resp.message(language_mappings[language]["error_occurred"])
        return str(resp)


@app.route("/handle_input", methods=["POST"])
def handle_input():
    language = request.args.get("language", session.get("language", "en"))
    print("language in handle_input:", language)
    global predictionState, conversation_history
    try:
        logger.info("handle_input called")

        user_input = request.form.get("SpeechResult")
        call_sid = request.form.get("CallSid")
        to_number = request.form.get("To")

        twiml = VoiceResponse()

        if not user_input:
            logger.warning("No speech input received")
            ai_response = language_mappings[language]["didnt_catch"]
        else:
            logger.info(f"User input: {user_input}")

            user_history = load_user_history(to_number)

            # Store user input in conversation history
            if call_sid not in conversation_history:
                conversation_history[call_sid] = []
            conversation_history[call_sid].append(
                {"speaker": "user", "text": user_input}
            )

            try:
                current_node = decisionTree[predictionState]
                current_question = current_node["question"]
                interpreted_response = interpret_response(user_input, current_node)

                # Still update user information if doesn't answer question
                new_user_history = update_user_history(
                    current_question, user_input, user_history
                )
                if interpreted_response == "invalid":
                    ai_response = rephrase_question(
                        current_question, user_input, True, new_user_history
                    )
                else:
                    if interpreted_response in current_node:
                        predictionState = current_node[interpreted_response]
                    else:
                        ai_response = f"{language_mappings[language]['couldnt_understand']} {current_question}"

                    if predictionState not in decisionTree:
                        ai_response = language_mappings[language][
                            "consult_professional"
                        ].format(predictionState)
                        logger.info(f"AI response: {ai_response}")
                        redirect_url = finalize_call(user_history)
                        s3_url = text_to_speech(ai_response, language)

                        if language != 'en':
                            twiml.pause(length=7)  

                        if s3_url:
                            twiml.play(s3_url)
                        else:
                            twiml.say(ai_response)

                        twiml.hangup()
                        return str(twiml)
                    else:
                        next_question = decisionTree[predictionState]["question"]
                        ai_response = rephrase_question(
                            next_question, user_input, False, user_history
                        )

                logger.info(f"AI response: {ai_response}")

                if ai_response.lower() == "stop call":
                    redirect_url = finalize_call(user_history)
                    ai_response = language_mappings[language]["thank_you"]
                    twiml.say(ai_response)
                    twiml.hangup()
                    return redirect(redirect_url)
                else:
                    s3_url = text_to_speech(ai_response, language)

                    if language != 'en':
                        twiml.pause(length=7)  

                    if s3_url:
                        twiml.play(s3_url)
                    else:
                        twiml.say(ai_response)

                save_user_history(to_number, user_history)
            except Exception as e:
                logger.error(f"Error processing input: {str(e)}")
                ai_response = language_mappings[language]["error_processing"]
                twiml.say(ai_response)

                redirect_url = finalize_call(user_history)
                twiml.hangup()
                return redirect(redirect_url)

            # Store AI response in conversation history
            conversation_history[call_sid].append(
                {"speaker": "ai", "text": ai_response}
            )

        # Always add a new Gather unless we're hanging up
        if "hangup" not in twiml.verbs:
            print("language in gather:", language)
            gather = Gather(
                input="speech",
                language=language_mappings[language]["gather_language"],
                action=f"{ngrok_url}/handle_input?language={language}",
                method="POST",
                speechTimeout=1,
                timeout=8,
            )
            twiml.append(gather)
            print("twiml in gather")

        logger.info(f"Returning TwiML: {twiml}")

        # Update the call with the new TwiML
        if call_sid:
            try:
                client.calls(call_sid).update(twiml=str(twiml))
                logger.info(f"Updated call {call_sid} with new TwiML")
            except Exception as e:
                logger.error(f"Error updating call {call_sid}: {str(e)}")
        else:
            logger.warning("No CallSid provided, skipping call update")

        return str(twiml)

    except Exception as e:
        logger.error(f"Error in handle_input: {str(e)}", exc_info=True)
        twiml = VoiceResponse()
        error_message = language_mappings[language]["error_occurred"]
        twiml.say(error_message)
        twiml.hangup()

        redirect_url = finalize_call(user_history)

        # Send a text message to continue the conversation
        client.messages.create(
            body=f"{error_message} The call has been disconnected due to unknown issues. Please text this number to continue the conversation.",
            from_=twilio_phone_number,
            to=to_number,
        )

        return redirect(redirect_url)


@app.route("/stream/<call_sid>")
def stream(call_sid):
    def event_stream():
        last_message_index = 0
        while True:
            if call_sid in conversation_history:
                current_messages = conversation_history[call_sid]
                if last_message_index < len(current_messages):
                    for message in current_messages[last_message_index:]:
                        yield f"data: {json.dumps(message)}\n\n"
                    last_message_index = len(current_messages)
            time.sleep(0.5)

    return Response(
        stream_with_context(event_stream()), content_type="text/event-stream"
    )


# Utility to read the JSON file
def read_medical_record(file_path):
    if os.path.exists(file_path):
        with open(file_path, "r") as file:
            return json.load(file)
    return {}


# Utility to write to the JSON file
def write_medical_record(data, file_path):
    with open(file_path, "w") as file:
        json.dump(data, file, indent=4)


def add_entry_to_medical_record(new_entries, file_path):
    # Read the existing record
    record = read_medical_record(file_path)
    # Get the current time
    current_time = datetime.now().strftime(
        "%m/%d/%Y %I:%M%"
    )  # Add the new entry using the current time as the key
    record["entries"].append({current_time: new_entries})
    # Write the updated record back to the JSON file
    write_medical_record(record, file_path)


@app.route("/medical-record", methods=["GET"])
def medical_record():
    # Get the phone number from query parameters
    phone_number = request.args.get("phone_number")

    if not phone_number:
        return "Phone number is required", 400

    # Sanitize the phone number to prevent directory traversal
    phone_number = "".join(filter(str.isalnum, phone_number))

    # Construct the JSON file path -- need + beforehand because queryargs doesn't accept +
    json_file = f"user_history_+{phone_number}.json"
    json_file_path = os.path.join(app.root_path, "static", "user_data", json_file)
    # Read the medical record data from the JSON file
    record = read_medical_record(json_file_path)

    # Render the medical-record.html template and pass the record data
    return render_template("medical-record.html", record=record)


@app.route("/set_language", methods=["POST"])
def set_language():
    language = request.form.get("language")
    session["language"] = language
    return redirect(url_for("login"))


@app.template_filter("remove_trailing_punctuation")
def remove_trailing_punctuation(text):
    return re.sub(r"[.!?]+$", "", text)


@app.route("/call_status", methods=["POST"])
def call_status():
    call_sid = request.form.get("CallSid")
    call_status = request.form.get("CallStatus")
    to_number = request.form.get("To")

    if call_status in ["completed", "busy", "no-answer", "failed", "canceled"]:
        print("Call status:", call_status)
        user_history = load_user_history(to_number)
        finalize_call(user_history)
        save_user_history(to_number, user_history)

        # Store the call status and medical record URL
        if call_sid not in conversation_history:
            conversation_history[call_sid] = []
        conversation_history[call_sid].append(
            {
                "type": "call_status",
                "status": call_status,
                "medical_record_url": url_for(
                    "medical_record", phone_number=to_number[1:]
                ),
            }
        )

    print("Call status:", call_status)
    return "", 204  # No content response


@app.route("/submit_webform", methods=["POST"])
def submit_webform():
    # Get form data
    first_name = request.form.get("first_name")
    last_name = request.form.get("last_name")
    phone_number = request.form.get("phone_number")
    dob = request.form.get("dob")
    gender = request.form.get("gender")
    height = request.form.get("height")
    weight = request.form.get("weight")
    reason = request.form.get("reason")

    # Calculate age from DOB
    birth_date = datetime.strptime(dob, "%Y-%m-%d")
    today = datetime.now()
    age = (
        today.year
        - birth_date.year
        - ((today.month, today.day) < (birth_date.month, birth_date.day))
    )

    # Process reason for visit with GPT
    gpt_prompt = f"Given the following description of a patient's reason for visit, extract and convert it into a concise, organized bulleted list of symptoms and concerns. Do not use 'You' or 'Your' in the response. '{reason}'"
    processed_reason = generate_openai_response(gpt_prompt)

    if processed_reason:
        processed_reason = processed_reason.strip().split("\n")
    else:
        processed_reason = [
            f"- {reason}"
        ]  # Fallback to original reason if GPT processing fails

    # Construct the JSON file path
    json_file = f"user_history_{phone_number}.json"
    json_file_path = os.path.join(app.root_path, "static", "user_data", json_file)

    # Read existing user history
    user_history = read_medical_record(json_file_path)

    # Update user information
    user_history["fname"] = first_name
    user_history["lname"] = last_name
    user_history["age"] = str(age)
    user_history["gender"] = gender
    user_history["height"] = height
    user_history["weight"] = weight
    user_history["phone_number"] = phone_number

    # Add new entry
    current_time = datetime.now().strftime("%m/%d/%Y %I:%M%p")
    new_entry = {current_time: ["- Patient filled out webform."] + processed_reason}

    if "entries" not in user_history:
        user_history["entries"] = []
    user_history["entries"].append(new_entry)

    # Write updated user history back to file
    write_medical_record(user_history, json_file_path)

    # Redirect to medical history page
    return redirect(
        url_for("medical_record", phone_number=phone_number[1:])
    )  # Remove leading '+' for URL


# Ensure these utility functions are defined:


def read_medical_record(file_path):
    if os.path.exists(file_path):
        with open(file_path, "r") as file:
            return json.load(file)
    return {}


def write_medical_record(data, file_path):
    with open(file_path, "w") as file:
        json.dump(data, file, indent=4)


if __name__ == "__main__":
    app.run(debug=True)
