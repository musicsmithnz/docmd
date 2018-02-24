#!/usr/bin/python3
import json
import subprocess
from tabulate import tabulate
#from collections import OrderedDict #might not be needed
import sys
import shlex
import re
import time
import paramiko#used for ssh
import numpy as numpy#used for matrix transposition for tabular data
import datetime#used for timestamp on file name generation
import cmd #used for REPEL
from urllib.error import HTTPError



#[One dict for all globals]
g = {
	'droplet_matrix'	:	[],
	'continue_repl'		:	True
}

class DOManagementShell(cmd.Cmd):
	intro = 'Welcome to the Digital Ocean Management Shell'

class SSHManagementShell(cmd.Cmd):
	intro = 'The commands you type will be run on the droplets with the IDs you selected'
	prompt = 'ssh>'


def update_data():
	print("checking for your droplets on the server...")
	droplet_matrix	=	[]
	#imports the raw data into a json object
	cmd_get_json	=	shlex.split("doctl compute droplet list --output json")
	proc_get_json	=	subprocess.Popen(cmd_get_json, stderr=subprocess.PIPE,stdout=subprocess.PIPE)
	try:
		out, err=	proc_get_json.communicate(timeout=5)
	except subprocess.TimeoutExpired:
		out, err=	proc_get_json.communicate()
		proc_get_json.kill()
	out=out.decode('utf-8')
	print("type(out)",type(out))
	json_droplets	=	json.loads(out)
	print("type(json_droplets)",type(json_droplets))
	print("json_droplets != None",json_droplets != type(None))
	if out.find('error') == -1:
		if type(json_droplets) != type(None):
#			if json_droplets:
			#puts the json information for each json droplet into a data matrix
			for json_droplet in enumerate(json_droplets):
				droplet_info=[]
				droplet_info.append(json_droplet[1]["id"])
				droplet_info.append(json_droplet[1]["networks"]["v4"][0]["ip_address"])
				droplet_info.append(json_droplet[1]["region"]["slug"])
				droplet_info.append(json_droplet[1]["name"])
				droplet_info.append(json_droplet[1]["image"]["name"])
				droplet_info.append(json_droplet[1]["image"]["distribution"])
				droplet_info.append(json_droplet[1]["size_slug"])
				droplet_matrix.append(droplet_info)
	else:
		print("there was an error contacting the server...")
	return droplet_matrix

def list_available(arg1,sort_index=1):
	command		=	shlex.split("doctl compute "+arg1+" list")
	proc		=	subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
	try:
		out,err	=	proc.communicate(timeout=15)
	except TimeoutExpired:
		proc.kill()
		out,err	=	proc.communicate()
	out=out.decode("utf-8")
#	if not out['errors']:
	r		=	re.sub('\t{2,5}','\t',out)
	info_headers	=	r.splitlines()[0].split('\t')
	info_headers.insert(0,'index')
	info_matrix	=	[s.split('\t')[:6] for s in r.splitlines()[1:]]
	if sort_index:
		info_matrix	=	sorted(info_matrix, key=lambda info_line: info_line[sort_index])
	return (info_matrix, info_headers) 

def interactive_select(option,sort_index=1):

	waiting_for_valid_input=True
	
	info_matrix, info_headers = list_available(option, sort_index)
	print(tabulate(info_matrix, headers=info_headers, showindex='always', tablefmt='fancy_grid'))
	while waiting_for_valid_input:
		user_input=input("please select an index to choose a(n) "+option+":\t")
		print("")
		try:
			info_index=int(user_input)
			if 0 <= info_index <= len(info_matrix):
				info_id=info_matrix[info_index][0]
				print("You have selected '",info_matrix[info_index],"'-",info_matrix[info_index][1],"...\n")
				waiting_for_valid_input=False
			else:
				print("the index must be between 0 and ",len(info_matrix),":\t")
		except:
			print("the index is in the leftmost column!")
	return info_id

def print_droplet_summary():
	update_data()
	global g
	g['droplet_matrix']
	print("currently available droplets:")
	print(tabulate(g['droplet_matrix'],tablefmt="fancy_grid"))

def add_droplet():
	
	#DEFINE DROPLET SETTINGS
	region_id	=	interactive_select('region',2)
	image_id	=	interactive_select('image',3)
	size_id		=	interactive_select('size',5)
	timestamp	=	datetime.datetime.now().timestamp()
	print("timestamp calculated to be ",timestamp,", using this in the sshkey name...\n")
	timestamp	=	str(timestamp).replace(".","")
	file_name	=	image_id+"-"+timestamp
	file_directory	=	"/home/raymond/.ssh/digitalocean/"

	#CREATE SSH KEY:
	file_path	=	file_directory+file_name
	print("creating SSHKey now...")
	proc_ssh_key	=	subprocess.Popen(["ssh-keygen", "-t", "rsa","-N","","-f",file_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	time.sleep(5)
	print("SSH Key saved in ",file_path,"...\n")
	
	#ASSIGN KEYS: 
	print("importing sshkey now...")
	import_ssh_key	=	"doctl compute ssh-key import "+file_name+"_key --public-key-file "+file_path+".pub"
	proc_ssh_key	=	subprocess.Popen(shlex.split(import_ssh_key), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	try:
		print("trying to communicate with sshkey import process...")
		out,err	=	proc_ssh_key.communicate(timeout=15)
		print("communication should have been made...")
	except TimeoutExpired:
		proc_ssh_key.kill()
		out,err	=	proc_ssh_key.communicate()
		print("failed to communicate with the sshkey import process...")
		print("stderr gives the value of: ",err)
	ssh_key_info	=	out.decode("utf-8")
	time.sleep(3)
	print("stderr gives the value of: ",err.decode("utf-8"))

	
	#GET_FINGERPRINT
	if ssh_key_info:
		print("ssh_key_info:\t",ssh_key_info)
		fingerprint	=	ssh_key_info.splitlines()[1].split('\t')[2]
		print('the ssh-key fingerprint is:\t',fingerprint)
		
		#CREATE_DROPLET_WITH_FINGERPRINT:
		create_command	=	"doctl compute droplet create "+file_name+" --size "+size_id+" --image "+image_id+" --region "+region_id+" --ssh-keys "+fingerprint
		proc_create	=	subprocess.Popen(shlex.split(create_command),stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		try:
			out,err	=	proc_create.communicate(timeout=10)
			rc	=	proc_create.returncode
		except TimeoutExpired:
			proc_create.kill()
			out,err	=	proc_create.communicate()
			rc	=	proc_create.returncode
		out=out.decode("utf-8")
		if rc == 0:
			print(out)
		#	print("succesfully added droplet:\n",tabulate(out,tablefmt='fancy_grid'))
		else:
			print("the droplet was unable to be created, it returned with return code '", rc,"' and stderr ",err,"\n")
	else:
		print("sshkey was not created, the error returned was this:\n",err.decode("utf-8"))

def delete_droplet(*args):
	user_input=""
	delete_more=True
	while delete_more:
		droplet_id=interactive_select("droplet",3)
		#user_input=input("enter the id of the droplet you wish to delete or q to quit this menu:")
		if user_input=="q":
			delete_more=False
		else:	
			delete_droplet_cmd=shlex.split("doctl compute droplet delete "+droplet_id)
			delete_proc=subprocess.Popen(delete_droplet_cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
			print("delete_droplet_cmd",delete_droplet_cmd)
			print(delete_proc.stderr.read().decode("utf-8"))
			out, err = delete_proc.communicate()
			delete_proc.kill()
		out, err = out.decode("utf-8"),err.decode("utf-8")
		print("output:\t",out)
		print("error:\t",err)

def run():
	pass

def ssh(ids,*script):
	print("arg1:",arg1)
	ssh = paramiko.SSHClient()
	ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
	ssh.connect('127.0.0.1', username='raymond', password='10.paint$RAY.01')
	stdin, stdout, stderr = ssh.exec_command("uname -a")
	out=stdout.readlines()
	print(out)

def quit():
	print("quit...")
	sys.exit()

g['alias_cmd_list'] = [
	'h',
	'p',
	'a',
	'd',
	'r',
	's',
	'q']

g['cmd_list'] = [
	'help',
	'print',
	'add a droplet',
	'delete a droplet',	
	'run a script',
	'ssh',
	'quit']

def help_menu():
	global g
	cmd_list_menu=numpy.transpose([g['alias_cmd_list'],g['cmd_list']])
	return "help:\n"+tabulate(cmd_list_menu,tablefmt='fancy_grid')

g['func_list'] = [
	help_menu,
	print_droplet_summary,
	add_droplet,
	delete_droplet,
	run,
	ssh,
	quit]

g['droplet_matrix'] = update_data()
print(help_menu())
while g['continue_repl']:
	failed_attempts=0
	print("please enter a command...")
	g['cmd'] = input().strip()
	user_input = g['cmd'].split(' ')
	cmd = user_input[0]
	if cmd in g['alias_cmd_list']:
		failed_attempts=0
		if len(user_input)>1:
			cmd_args = []
			for arg in user_input[1:]:
				cmd_args.append(arg)
			g['func_list'][g['alias_cmd_list'].index(cmd)](cmd_args)
			print("command was called")
		else:
			g['func_list'][g['alias_cmd_list'].index(cmd)]()
	else:
		print("please enter appropriate input")
		failed_attempts=failed_attempts+1
		if(failed_attempts>=3):
			g['continue_repl'] = False
