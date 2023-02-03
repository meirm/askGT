#!/usr/bin/env python
"""
askGPT is a simple command line tool for interacting with OpenAI's API.
It is based on the example provided by OpenAI at https://beta.openai.com/docs/developer-quickstart/1-introduction
Date: 2023/01/23
"""
__title__ = 'askGPT'
__author__ = 'Meir Michanie'
__license__ = 'MIT'
__credits__ = ''
__version__ = "0.4.12"


import os
from .api.openai import ChatGPT
from .config import Config, basicConfig
import click
from rich import print
import backoff
import time
import toml
import platform
import subprocess
from .shell import Shell
from .tools import eprint, sanitizeName
# from rich.console import Console
# console = Console()

# use pyreadline3 instead of readline on windows
is_windows = platform.system() == "Windows"
if is_windows:
    import pyreadline3  # noqa: F401
else:
    import readline

pass_config = click.make_pass_decorator(Config, ensure=True)

@click.group()
@click.version_option(__version__)
@pass_config
def cli(config):
    if config.progConfig.get("showDisclaimer",True):
        print(config.disclaimer)

@cli.command()
@pass_config
def disclaimer(config):
    """Show the disclaimer"""
    if not config.progConfig.get("showDisclaimer",False):
        print(config.disclaimer)

@cli.command()
@pass_config

def shell(config):
    """Use the cmd module to create an interactive shell where the user can all the commands such as query, edit, config, show. We will call a class which we will write later as a child of cmd.cmd"""
    shell = Shell(config)
    shell.cmdloop()



@cli.command()
@pass_config
@click.option("--set", help="configuration to change")
@click.option("--value", help="AI prompt")
def config(config, set, value):
    """
Change config values"""
    if set:
        if set in config.progConfig:
            config.updateParameter(set, value)
        else:
            print(f"Can't set {set} to {value}. {set} is not a valid configuration value")
    jsonConfig = {'name':'askGPT','default':config.progConfig}
    print(toml.dumps(jsonConfig))
    with open(os.path.join(config.settingsPath,"config.toml"), 'w') as f:
        toml.dump(jsonConfig,f)
        

@cli.command()
@click.option("--subject", "-s", default="quest1", help="The subject of the query. This is used to determine the model to use.")
@click.option("--scenario", "-sc", default="Zork", help="The scenario of the query. This is used to determine the model to use.")
@click.option("--prompt", "-p", default="You are in a maze of twisty little passages, all alike.", help="The prompt to use for the query.")
@click.option("--max_tokens", "-m", default=64, help="The maximum number of tokens to return.")
@pass_config
def query(config, subject, scenario, prompt, max_tokens):
    """Query the model for a response."""
    print(config.chatGPT.query(subject, scenario, prompt, max_tokens))


@cli.command()
@pass_config
@click.option("--subject", prompt="Subject", help="Subject to use to save the conversation")
@click.option("--submit", is_flag=True, help="Submit the dialog")
@click.option("--scenario", default="Neutral", help="scenario to use in the conversation")

def edit(config,subject,submit, scenario):
    """
Edit a conversation"""
    subject = sanitizeName(subject)
    lines = list()
    if os.path.isfile(os.path.join(config.conversations_path, subject + config.fileExtention)):
        with open(os.path.join(config.conversations_path, subject + config.fileExtention), "r") as f:
            lines = f.readlines()
    lines = click.edit("".join(lines))
    if lines is not None:
        with open(os.path.join(config.conversations_path, subject + config.fileExtention), "w") as f:
            f.write(lines)
    if submit:
        config.chat.submitDialog(config,subject, scenario)

@cli.command()
@pass_config
@click.option("--subject", prompt="Subject", help="Subject to use to save the conversation")
@click.option("--scenario", default="Neutral", help="scenario to use in the conversation")
@click.option("--temperature", default=basicConfig["temperature"], type=float, help="Set alternative temperature")
def train(config, subject, scenario, temperature):
    """Train the model with the conversation"""
    config.progConfig["temperature"] = temperature
    config.chat.submitDialog(config, subject, scenario)

@cli.command()
@pass_config
@click.option("--subject", prompt="Subject", help="Subject to use to save the conversation")
@click.option("--scenario", default="Neutral", help="scenario to use in the conversation")
@click.option("--temperature", default=basicConfig["temperature"], type=float, help="Set alternative temperature")
def submit(config, subject, scenario, temperature):
    """Submit without editing the scenario file to openAi api and print out the response."""
    config.progConfig["temperature"] = temperature
    config.chat.submitDialog(config, subject, scenario)




@cli.command()
@pass_config
@click.argument("whatToShow", default="config")
@click.argument("subject", default="" )
def show(config, whattoshow, subject):
    """Show config|scenarios|subjects or the conversation inside a subject."""
    if subject == "":
        if whattoshow == "config":
            print("Current configuration:")
            print(toml.dumps(config.progConfig))
        elif whattoshow == "subjects":
            print("Current subjects:")
            for subject in config.get_list():
                    print(subject)
        elif whattoshow == 'scenarios':
            print("Current scenarios:")
            for scenario in config.scenarios.keys():
                print(scenario)
        elif whattoshow == 'models':
            print("Current models:")
            for model in sorted(list(map(lambda n: n.id,config.chat.Model.list().data))):
                print(model)
        else:
            print("Please specify what to show. Valid options are: config, subjects, scenarios, subject")
            print("In case of passing the option 'subject' please pass as well the subject's name")
    else:
        if os.path.isfile(os.path.join(config.settingsPath, 'conversations', subject + config.fileExtention)):
            with open(os.path.join(config.settingsPath, 'conversations', subject + config.fileExtention), 'r') as f:
                print(f.read())
        else:
            eprint("Subject not found")


@cli.command()
@pass_config
def credentials(config):
    """
Save the API keys to query OpenAI"""
    print("Welcome to askGPT")
    print("Please provide your OpenAI API key and organization")
    print("You can find these values at https://beta.openai.com/account/api-keys")
    config.chat.api_key = input("API_KEY:")
    config.chat.organization = input("ORGANIZATION:")
    with open(os.path.join(config.settingsPath, "credentials"), "w") as f:
        f.write(config.chat.api_key + ":" + config.chat.organization)
    print("askGPT is now ready to use")


@pass_config
@cli.command()
@pass_config
@click.option("--subject", help="Subject of the conversation")
@click.option("--all/--single",  default=False, help="Delete all archived conversations")
def delete(config, subject, all):
    """
Delete the previous conversations saved by askGPT"""
    if all:
        for subject in config.get_list():
            os.remove(os.path.join(config.conversations_path, subject + config.fileExtention))
    elif subject and os.path.isfile(os.path.join(config.conversations_path,sanitizeName(subject) + config.fileExtention)):
        os.remove(os.path.join(config.conversations_path, subject + config.fileExtention))
    else:
        eprint("No chat history with that subject")
        return

@cli.command()
@pass_config
@click.option("--subject", prompt="Subject", help="Subject of the conversation")
@click.option("--enquiry", prompt="Enquiry", help="Your question")
@click.option("--scenario", default="Neutral", help="scenario to use in the conversation")
@click.option("--model", default=basicConfig["model"], help="Set alternative model")
@click.option("--temperature", default=basicConfig["temperature"], type=float, help="Set alternative temperature")
@click.option("--top-p", default=basicConfig["topP"], type=int, help="Set alternative topP")
@click.option("--frequency-penalty", default=basicConfig["frequencyPenalty"], type=float, help="Set alternative frequencyPenalty")
@click.option("--presence-penalty", default=basicConfig["presencePenalty"], type=float, help="Set alternative presencePenalty")
@click.option("--max-tokens", default=basicConfig["maxTokens"], type=int, help="Set alternative maxTokens")
@click.option("--verbose", is_flag=True, help="Show verbose output or just the answer")
@click.option("--save/--no-save", default=True, help="Save the conversation")
@click.option("--retry", is_flag=True, help="In case of error retry the post.")
@click.option("--execute", is_flag=True, help="Parse the AI response and execute it")
def query(config, subject, enquiry, scenario,model, temperature,max_tokens, top_p,  frequency_penalty, presence_penalty, verbose, save, retry, execute): 
    """
Query the OpenAI API with the provided subject and enquiry"""
    enquiry = config.progConfig["userPrompt"] + enquiry
    if subject:
        with open(os.path.join(config.conversations_path, sanitizeName(subject) + config.fileExtention), "a") as f:
            pass
        with open(os.path.join(config.conversations_path, sanitizeName(subject) + config.fileExtention), "r") as f:
            chatRaw = f.read()
            bootstrappedChat = config.chat.bootStrapChat(config, scenario)
            chat = bootstrappedChat + "\n" + chatRaw  + enquiry + "\n" + config.progConfig["aiPrompt"]
            tries = 1
            if retry:
                tries = config.progConfig.get("maxRetries",1)
            success = False
            sleepBetweenRetries = config.progConfig["retryDelay"]
            while tries > 0:
                try:
                    response = config.chat.completions_with_backoff(
                        delay_in_seconds=config.delay,
                        model=model,
                        prompt=chat,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        top_p=top_p,
                        frequency_penalty=frequency_penalty,
                        presence_penalty=presence_penalty,
                        stop=[ # "\n",
                        config.progConfig["userPrompt"], config.progConfig["aiPrompt"]],
                    )
                    ai = response.choices[0].text
                    if ai.startswith("\n\n"):
                        ai = ai[2:]
                    success = True
                    break
                except Exception as e:
                    tries -= 1

                    if str(e) == "openai.error.RateLimitError":
                        eprint("Error: Too many requests. We will try again")
                    eprint("Error: " + str(e))
                    eprint(f"Retrying again in {sleepBetweenRetries} seconds...")
                    time.sleep(sleepBetweenRetries)
                    sleepBetweenRetries *= config.progConfig["retryMultiplier"] 
                    if sleepBetweenRetries > config.progConfig["retryMaxDelay"]:
                        sleepBetweenRetries = config.progConfig["retryMaxDelay"]
        if success == False:
            eprint("Error: Too many requests. Please wait a few minutes and try again")
            return
        if save:               
            with open(os.path.join(config.conversations_path, sanitizeName(subject) + config.fileExtention), "a") as f:
                f.write(enquiry) 
                f.write("\n")
                f.write(config.progConfig["aiPrompt"] + ai)
                f.write("\n")
                f.close()
        if execute:
            editPrompt = click.prompt(f"{ai}\nedit command? [y/n]", type=click.Choice(["y", "n"]), default="n")
            if editPrompt == "y":
                edited = click.edit(ai)
                if edited:
                    ai = edited
            doExec = click.prompt(f"{ai}\nExecute command? [y/n]", type=click.Choice(["y", "n"]), default="y")
            """execute the command in the terminal and edit the response before saving it."""
            if doExec == "y":
                result  = subprocess.run(ai, stdout=subprocess.PIPE, shell=True, stderr=subprocess.STDOUT)
                result = result.stdout.decode("utf-8")
                print(result)
                saveOutput = click.prompt(f"save output? [Y/e/n]", type=click.Choice(["y", "e", "n"]), default="y")
                if saveOutput == "e":
                    edited = click.edit(result.stdout.decode("utf-8"))
                    if edited:
                        result = edited
                if saveOutput != "n":
                    with open(os.path.join(config.conversations_path, sanitizeName(subject) + config.fileExtention), "a") as f:
                        f.write(config.progConfig["userPrompt"] + str(result))
                        f.write("\n")
                        f.close()
        else:
            if verbose:
                print(chat + ai)
            else:
                print(ai)
    else:
        print("No subject provided")
        return
    
    #  print("The askGPT is sleeping. [bold red]Next time, rub the lamp first.[/bold red]")

