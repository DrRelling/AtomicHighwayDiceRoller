import logging
import json
import random

from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError

import azure.functions as func


def main(req: func.HttpRequest) -> func.HttpResponse:
    """A quick Discord interaction to make it easy to roll dice for Atomic Highway games.

    Args:
        req (func.HttpRequest): Takes a HTTP request...

    Returns:
        func.HttpResponse: ...and returns one, as you'd expect.
    """
    logging.info("Python HTTP trigger function processed a request.")

    PUBLIC_KEY = "" # remove this before commit!

    verify_key = VerifyKey(bytes.fromhex(PUBLIC_KEY))

    signature = req.headers["X-Signature-Ed25519"]
    timestamp = req.headers["X-Signature-Timestamp"]

    try:
        verify_key.verify(f"{timestamp}{req.get_body().decode('utf-8')}".encode(), bytes.fromhex(signature))
    except BadSignatureError:
        return func.HttpResponse("invalid request signature", status_code=401)

    req_body = req.get_json()

    if req_body["type"] == 1:
        # this is just an "are you there?" request from discord, respond with "yes"
        return func.HttpResponse(json.dumps({"type": 1}), status_code=200, mimetype="application/json", headers={"content-type": "application/json"})
    else:
        options = req_body["data"]["options"]
        attribute = options[0]["value"]
        # attributes max out at 10, so cap that
        if attribute > 10:
            attribute = 10
        if len(options) == 1:
            # this is an attribute-only roll
            dice_results = roll_dice(attribute)
            content = "Dice result: " + nums_to_str(dice_results["natural_results"])
            if len(dice_results["reroll_results"]) > 0:
                content += " | Bonus result: " + nums_to_str(dice_results["reroll_results"])
        else:
            # this is a skill roll
            # option 2 is the skill points, and option 3 is the (optional) number of repetitions
            # if we don't have a repeat parameter, or it doesn't make sense, default to 1 repetition
            if len(options) == 3:
                repeat = options[2]["value"]
                if repeat < 1 or repeat > 10:
                    repeat = 1
            else:
                repeat = 1
            # build response string
            content = ""
            for i in range(repeat):
                # reseed on each repetition - this is just a game, so we don't need to worry about serious randomness
                random.seed()
                dice_results = roll_dice(attribute)
                skill_points = options[1]["value"]
                results_with_skill_points = apply_skill_points(dice_results, skill_points)
                successes = total_successes(results_with_skill_points)
                # got to get that plural right or people will complain about it!
                if successes == 1:
                    success_word = " success"
                else:
                    success_word = " successes"
                content += "**" + str(successes) + success_word + "!**\nDice result: " + nums_to_str(dice_results["natural_results"]) 
                content += " | Skill points: " + str(skill_points) + " | Results w/skill points: " + nums_to_str(dice_results["with_skill_results"])
                if len(dice_results["reroll_results"]) > 0:
                    content += " | Bonus result: " + nums_to_str(dice_results["reroll_results"])
                if i+1 < repeat:
                    content += "\n"

        response = json.dumps({
            "type": 4,
            "data": {
                "content": content 
            }
        })
        return func.HttpResponse(response, status_code=200, mimetype="application/json", headers={"content-type": "application/json"})

def nums_to_str(arr): 
    """Quick helper to convert an array of numbers to strings.

    Args:
        arr (int): Array of numbers

    Returns:
        arr (string): Array of strings
    """
    return ", ".join([str(x) for x in arr])

def roll_dice(no_of_dice):
    """Roll a number of dice.

    Args:
        no_of_dice (int): Number of dice to roll.

    Returns:
        dict: Dictionary with an array of natural results and bonus results from rerolls.
    """
    results = {
        "natural_results": [],
        "reroll_results": []
    }
    for _ in range(no_of_dice):
        result = generate_dice_result()
        results["natural_results"].append(result["natural_result"])
        results["reroll_results"] += result["reroll_results"]
    results["natural_results"].sort(reverse=True)
    results["reroll_results"].sort(reverse=True)
    return results


def generate_dice_result():
    """Generate results for a single die roll. In Atomic Highway, if we roll a six, we add that to the results and get to roll again. 

    Returns:
        dict: Dictionary containing the original die roll and any bonus numbers we got from rolling sixes.
    """
    natural_result = -1
    reroll_results = []
    for _ in range(100):
        result = random.randint(1,6)
        if natural_result == -1:
            natural_result = result
        else:
            reroll_results.append(result)
        if result != 6:
            break
    return {
        "natural_result": natural_result,
        "reroll_results": reroll_results
    }
        

def apply_skill_points(dice_results, skill_points):
    sorted_results = sorted(dice_results["natural_results"], reverse=True)
    
    results = []
    for result in sorted_results:
        if result == 6:
            results.append(6)
            continue
        diff = 6 - result
        if diff <= skill_points:
            skill_points -= diff
            results.append(6)
        else:
            results.append(result + skill_points)
            skill_points = 0
    dice_results["with_skill_results"] = results
    return dice_results

def total_successes(dice_results):
    successes = 0
    for result in dice_results["reroll_results"] + dice_results["with_skill_results"]:
        if result == 6:
            successes += 1
    return successes
