#an integration is a plugin that executes a binary on the operating system that this agent is running on and turns its output into Nodes that are ingested by Secquiry

import collablio.node as cnode
import collablio.client as cclient
import filereadutils
import credentialmanager
import json

import random
import sys
import re
import os
import time

import copy
import datetime
import uuid
import traceback

import base64
import io

async def generate(metadata_dict):
    result = credentialmanager.save_credentials(metadata_dict)
    return result

