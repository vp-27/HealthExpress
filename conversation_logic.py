import json
import requests
import logging
import os
from dotenv import load_dotenv
from tree import decisionTree
from user_history import (
    load_user_history,
    save_user_history,
    add_entry_to_history,
    update_user_info,
)

load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variables
predictionState = "root"

openai_api_key = os.getenv("OPENAI_API_KEY")


def interpret_response(user_response, question_node):
    options = list(question_node.keys())
    options.remove("question")

    prompt = f"""
    Given the user response: "{user_response}"
    And the question: "{question_node['question']}"
    Interpret the response and categorize it into one of the following options: {', '.join(options)}
    If the response doesn't properly address the question, return "invalid".
    
    Please return only one option from the list above, not multiple options.
    """

    interpreted_response = generate_openai_response(prompt).strip().lower()

    # Post-processing to ensure only one option is returned
    if interpreted_response in options:
        return interpreted_response
    elif ',' in interpreted_response:
        # If multiple options are returned, take the first one
        first_option = interpreted_response.split(',')[0].strip()
        return first_option if first_option in options else "invalid"
    
    return "invalid"


def generate_openai_response(transcript):
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {openai_api_key}",
        "Content-Type": "application/json",
    }
    data = {
        "model": "gpt-4-turbo",
        "messages": [{"role": "user", "content": transcript}],
    }
    response = requests.post(url, headers=headers, json=data)
    logger.info(f"OpenAI response: {response.status_code}")
    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"]
    return None


def update_user_history(question, answer, user_history):
    prompt = f"""
    Given the question: "{question}"
    And the user's response: "{answer}"
    Extract the following information: fname, lname, age, gender, height, weight.
    Return the extracted information in the format: {{ "fname": <fname>, "lname": <lname>, "age": <age>, "gender": <gender>, "height": <height>, "weight": <weight> }}.
    If any information is not available, return null for that field.
    """
    gpt_response = generate_openai_response(prompt)

    try:
        extracted_info = json.loads(gpt_response)
        for key, value in extracted_info.items():
            if value is not None:
                update_user_info(user_history, key, value)
    except json.JSONDecodeError:
        logger.error("Failed to parse GPT response for user information.")

    # Generate bullet points for additional information
    prompt = f"""
    Given the question: "{question}"
    And the user's response: "{answer}"
    Create a concise bullet point summary of the key information in the response. Do not have redundancy.
    """
    gpt_response = generate_openai_response(prompt)
    bullet_points = [
        line.strip() for line in gpt_response.strip().split("\n") if line.strip()
    ]

    try:
        if isinstance(bullet_points, list):
            add_entry_to_history(user_history, bullet_points)
        else:
            logger.error("GPT response for bullet points is not a valid list.")
    except:
        logger.error("Failed to parse GPT response for bullet points.")
        add_entry_to_history(user_history, [f"Error processing: {answer}"])

    return user_history


def rephrase_question(
    original_question, user_response, invalid_response=False, user_history=None
):
    if user_history is None:
        user_history = {"entries": []}

    # Collect user history, formatted as bullet points
    user_history_list = []
    for entry in user_history["entries"]:
        for date, info in entry.items():
            user_history_list.extend([f"- {i}" for i in info])

    # Add current_call information to user_history_list
    if "current_call" in user_history:
        user_history_list.extend(
            [f"- Current Call: {call}" for call in user_history["current_call"]]
        )

    user_history_list.extend(
        [
            f"- Age: {user_history.get('age', 'N/A')}",
            f"- Gender: {user_history.get('gender', 'N/A')}",
            f"- Name: {user_history.get('fname', '')} {user_history.get('lname', '')}".strip(),
            f"- Weight: {user_history.get('weight', 'N/A')}",
            f"- Height: {user_history.get('height', 'N/A')}",
        ]
    )
    user_history_formatted = "\n".join(user_history_list)
    print(user_history_formatted)

    if invalid_response:
        context = f"""
        The user responded: "{user_response}", which was not understood or is invalid.

        You need to:
        1. Politely inform the user that their response ("{user_response}") is invalid (e.g., "Sorry, '{user_response}' is not a valid answer to the question.")
        2. Avoid repeating the user's response or asking an unrelated question.
        3. Rephrase the original question to provide more clarity or give the user guidance to answer correctly.
        4. Leverage previous conversations and the user's history to personalize the response.
        5. Make the response concise. Keep total response under 30 words.

        Example:
        Original Question: "How old are you?"
        Invalid Response: "Tuesday"
        User History:
        {user_history_formatted}
        Desired Output: "Sorry, 'Tuesday' is not a valid age. Can you please tell me how many years old you are?"

        Original Question: "{original_question}"
        Invalid Response: "{user_response}"
        User history: 
        {user_history_formatted}
        """
    else:
        context = f"""
        You will rephrase a question to be customized to a user's medical history.

        Rephrase the original question:
        1. Maintain the core intent of the original question.
        2. Ensure the rephrased question logically follows the context of the user's previous responses.
        3. Leverage previous conversations and user history to adapt the question for a personalized experience.
        4. Make the response concise.

        Respond ONLY with the rephrased question, without any additional text or labels.

        Example:
        Original Question: "What kind of exercise do you prefer?"
        User History: 
        {user_history_formatted}
        Desired Output: "Do you prefer hiking or cycling?"

        Original Question: "{original_question}"
        User history: 
        {user_history_formatted}
        """

    return generate_openai_response(context).strip('"')


def gpt_call(user_response, phone_number):
    global predictionState

    user_history = load_user_history(phone_number)

    current_node = decisionTree[predictionState]
    current_question = current_node["question"]
    interpreted_response = interpret_response(user_response, current_node)

    if interpreted_response == "invalid":
        rephrased_question = rephrase_question(
            current_question, user_response, True, user_history
        )
        return rephrased_question

    user_history = update_user_history(current_question, user_response, user_history)
    save_user_history(phone_number, user_history)

    if interpreted_response in current_node:
        predictionState = current_node[interpreted_response]
    else:
        return f"I couldn't understand your response. {current_question}"

    if predictionState not in decisionTree:
        return f"Based on your answers, you may have {predictionState}. Please consult a medical professional for proper diagnosis."

    next_question = decisionTree[predictionState]["question"]
    rephrased_question = rephrase_question(
        next_question, user_response, False, user_history
    )
    return rephrased_question


def terminal():
    print("Welcome to the medical diagnosis assistant.")
    print("Please answer the following questions.")

    phone_number = input("Please enter your phone number: ")
    user_history = load_user_history(phone_number)

    rephrased_question = rephrase_question(
        decisionTree["root"]["question"], "", False, user_history
    )
    print(rephrased_question)
    user_input = input("Your answer: ")

    while True:
        response = gpt_call(user_input, phone_number)
        print(response)

        if "Based on your answers" in response:
            break

        user_input = input("Your answer: ")

    print("\nYour medical history:")
    print(json.dumps(user_history, indent=2))


if __name__ == "__main__":
    terminal()
