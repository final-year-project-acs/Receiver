# -*- coding: UTF-8 -*-

import os
from flask import Flask, render_template
from flask import request
from flask_sqlalchemy import SQLAlchemy
import numpy
import base64
import time
import pickle
from datetime import datetime
#from db_tables import employees
import threading

import sys
sys.path.insert(1, '../config')
# insert at 1, 0 is the script path (or '' in REPL)

from hparam import hparam as hp

from aes_utils import AESCipher

key = 'this is my key'
aes_cipher = AESCipher(key)

# Initiating the Flask app
app = Flask(__name__)


# Configuring the database connection

if hp.app.ENV == 'dev':
    app.debug = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://' + \
    hp.app.dev_db_username + ':' + \
    hp.app.dev_db_password + '@' + \
    hp.app.dev_db_host +  ':5432' +'/' + \
    hp.app.dev_db_name
else:
    app.debug = False
    app.config['SQLALCHEMY_DATABASE_URI'] = ''

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
############################### Data Base tables ###############################

class employees(db.Model):
    __tablename__ = 'employees'
    id = db.Column(db.Text, primary_key=True, autoincrement=False) #, default=db.session.query(func.public.generate_uid(5)).all())
    employee_first_name = db.Column(db.String(50))
    employee_last_name = db.Column(db.String(50))
    employee_phone = db.Column(db.String(12),  unique=True)
    employee_proffession = db.Column(db.String(50))
    employee_banned = db.Column(db.Text, default='') # '' <==> not banned | not empty value <==> banned
    employee_role = db.Column(db.String(200), default='user')

    

    def __init__(self, employee_id, first_name, last_name, phone, proffession, banned, role):
        self.id = employee_id
        self.employee_first_name = first_name
        self.employee_last_name = last_name
        self.employee_phone = phone
        self.employee_proffession = proffession
        self.employee_banned = banned  # '' <==> not banned | not empty value <==> banned
        self.employee_role = role

class rooms(db.Model):
    __tablename__ = 'rooms'
    id = db.Column(db.Text, primary_key=True, autoincrement= False) # this is the door number (4 digits)
    room_description = db.Column(db.String(200), default= '')

    def __init__(self, num_door, room_description=''):
        self.id = num_door
        self.room_description = room_description

class has_access(db.Model):
    __tablename__ = 'has_access'
    employee_id = db.Column(db.Text, db.ForeignKey(employees.id), primary_key=True)
    room_id = db.Column(db.Text, db.ForeignKey(rooms.id), primary_key=True)
    date_has_access = db.Column(db.Date)
    time_has_access = db.Column(db.Time)
    description_has_access = db.Column(db.String(200))

    employee = db.relationship('employees', foreign_keys='has_access.employee_id')
    room = db.relationship('rooms', foreign_keys='has_access.room_id')

    def __init__(self, employee_id, room_id, date_has_access, time_has_access):
        self.employee_id = employee_id
        self.room_id = room_id
        self.date_has_access = date_has_access
        self.time_has_access = time_has_access

class log_inscription(db.Model):
    __tablename__ = 'log_inscription'
    id = db.Column(db.Integer, primary_key=True) #, default=db.session.query(func.public.generate_uid(5)).all())
    facial_biometric = db.Column(db.Text, unique=True) # path to preprocessed face data
    vocal_biometric = db.Column(db.Text, unique=True) # path to preprocessed voice data
    employee_id = db.Column(db.Text, db.ForeignKey(employees.id))

    date_inscription = db.Column(db.Date)
    time_inscription = db.Column(db.Time)
    inscription_description = db.Column(db.String(200), default='')

    employee = db.relationship('employees', foreign_keys='log_inscription.employee_id')

    def __init__(self, facial_biometric, vocal_biometric, employee_id, 
                date_inscription, time_inscription, inscription_description=''):
        self.facial_biometric = facial_biometric
        self.vocal_biometric = vocal_biometric
        self.employee_id = employee_id
        self.date_inscription = date_inscription
        self.time_inscription = time_inscription
        self.inscription_description = inscription_description


class log_verification(db.Model):
    __tablename__ = 'log_verification'
    employee_id = db.Column(db.Text, db.ForeignKey(employees.id), primary_key=True)
    room_id = db.Column(db.Text, db.ForeignKey(rooms.id), primary_key=True)
    date_verification = db.Column(db.Date, primary_key=True)
    time_verification = db.Column(db.Time, primary_key=True)
    verification_description = db.Column(db.String(200), default='')

    employee = db.relationship('employees', foreign_keys='log_verification.employee_id')
    room = db.relationship('rooms', foreign_keys='log_verification.room_id')

    def __init__(self, employee_id, room_id, date_verification, 
                    time_verification, verification_description=''):
        self.employee_id = employee_id
        self.room_id = room_id
        self.date_verification = date_verification
        self.time_verification = time_verification
        self.verification_description = verification_description


################################################################################
# To recreate an empty database call this function and it will do the job
def create_empty_db():
    db.drop_all()
    db.create_all()
    db.session.commit()

# create and insert new user
def insert_new_user(id_employee, first_name, last_name, phone='', proffession='', banned='', role='user'):
    employee = employees(id_employee, first_name, last_name, phone, proffession, banned, role)
    db.session.add(employee)
    db.session.commit()

def ban_user(employee_id):
    employee = employees.query.filter_by(id == employee_id).first()
    employee.employee_banned = datetime.now.strftime("%Y-%m-%d %H:%M:%S")
    db.session.commit()


def unban_user(employee_id):
    employee = employees.query.filter_by(id == employee_id).first()
    employee.employee_banned = ''
    db.session.commit()


# create and insert new room
def insert_room(room_id):
    room = rooms(room_id)
    db.session.add(room)
    db.session.commit()

# add new permission to user (to a given room)
def add_access_permission_user(id_employee, id_room):
    access_permission = has_access(id_employee, id_room, datetime.today().strftime('%Y-%m-%d'),
                                    datetime.now().strftime('%H:%M:%S'))
    db.session.add(access_permission)
    db.session.commit()

# verify if a given user have access to a building
def check_user_has_access(id_employee, room_number):
    access = db.session.query(has_access).filter(has_access.employee_id == id_employee, 
                    has_access.room_id == room_number).count()
    return False if access == 0 else True

# remove permission of user to a room
def remove_permession_user(id_employee, room_number):
    has_access.query.filter_by(employee_id == id_employee, room_id == room_number).delete()
    db.session.commit()

# inserting enrollment log
def insert_enrollment_log(face_path, voice_path, employee_id, 
                        inscription_date, inscription_time):
    log_inscription = log_inscription(face_path, voice_path, employee_id, inscription_date, inscription_time)
    db.session.add(log_inscription)
    db.session.commit()

# inserting verification log
def insert_verification_log(employee_id, room_id, verification_date, verification_time):
    log_verification = log_verification(employee_id, room_id, verification_date, verification_time)
    db.session.add()
    db.session.commit()


################################################################################


@app.route('/', methods = ['GET'])
def home():
    return render_template('home.html')#, STATE=state)

@app.route('/about', methods = ['GET'])
def about():
    return render_template('about.html')


##################################################################################################################################
##################################################################################################################################
##################################################################################################################################
##################################################################################################################################
##################################################################################################################################

door_number_digits = ""
best_identified_faces = []
best_identified_speakers = []

@app.route('/upload_verification', methods = ['POST'])
def upload_verify():

    start_rec = time.time()

    print('\n\n\n\n ########################### Incoming Verification ... ########################### ')

    if not request.form['IMG'] \
    or not request.form['AUDIO'] \
    or not request.form['timestamp']:
        return 'Données non complètes'

    # Decrpting data
    img_data_encoded = aes_cipher.decrypt(request.form['IMG'])
    audio_data_encoded = aes_cipher.decrypt(request.form['AUDIO'])
    timestamp = aes_cipher.decrypt(request.form['timestamp'])

    # Decoding image and audio data
    img_data = base64.b64decode(img_data_encoded)
    audio_data = base64.b64decode(audio_data_encoded)

    # Writing image data to disk
    img_file_name = timestamp + "_verify_photo.jpg"
    img_file_path = hp.integration.verify_upload_folder + img_file_name
    with open(img_file_path, 'wb') as f:
        f.write(img_data)
    
    # Writing audio data to disk
    audio_file_name = timestamp + "_verify_audio.m4a"
    audio_file_path = hp.integration.verify_upload_folder + audio_file_name
    with open(audio_file_path, 'wb') as f:
        f.write(audio_data)



    # -------------------------------------
    #           Face Verification
    # -------------------------------------

    def extract_face_and_identify():

        # Extracting face
        start_rf1 = time.time()
        err_code_rf1 = os.system("conda run -n pytorch_main python -W ignore " 
                                    + hp.integration.face_verification_path + "extract_face.py" 
                                    + " --input_image " + img_file_path 
                                    + " --destination_dir " + hp.integration.verify_upload_folder)
        end_rf1 = time.time() - start_rf1


        # Identifying face
        start_rf2 = time.time()
        err_code_rf2 = os.system("conda run -n vgg_py3 python -W ignore " 
                                    + hp.integration.face_verification_path + "identify_face.py" 
                                    + " --face_image " + img_file_path.replace(".jpg", "_visage.jpg") 
                                    + " --preprocessed_dir " + hp.integration.enroll_preprocessed_photo 
                                    + " --best_identified_faces ./ "
                                    + " 2> err_output_identify_face")
        end_rf2 = time.time() - start_rf2

        if (err_code_rf1 + err_code_rf2 == 0):
            # Clean execution of face extraction and face identification modules
            pass

        with open('./facial_result.data', 'rb') as filehandle:
            global best_identified_faces 
            best_identified_faces = pickle.load(filehandle)
        os.system("rm ./facial_result.data")
        
        id = best_identified_faces[0][0]
        score = best_identified_faces[0][1]
        lname_face = id.split('_')[2]
        fname_face = id.split('_')[3]

        print('\n\n    FACE RECOGNITION : '
            + '\n\t - Time to recognize face (total) : %f' % (end_rf1 + end_rf2) 
            + '\n\t    + Face extraction : %f' % (end_rf1) 
            + '\n\t    + Face identification : %f' % (end_rf2) 
            + '\n\t - Identified the face as : %s %s - (precision : %d%%)' % (lname_face, fname_face, int(100*score)))

    thread_face = threading.Thread(target=extract_face_and_identify)
    thread_face.start()



    # -------------------------------------
    #          Voice Verification
    # -------------------------------------

    def verify_speaker():

        # print('\t Verifying the voice...')

        start_rv = time.time()
        err_code_rv = os.system("conda run -n voice_py3 python -W ignore " 
                                    + hp.integration.speaker_verification_path + "verify_speaker.py" 
                                    + " --verify t " 
                                    + " --test_wav_file " + audio_file_path
                                    + " --best_identified_speakers ./")
        end_rv = time.time() - start_rv

        if (err_code_rv == 0):
            # Clean execution of voice extraction module
            pass

        with open('./speaker_result.data', 'rb') as filehandle:
            global best_identified_speakers
            best_identified_speakers = pickle.load(filehandle)
        os.system("rm ./speaker_result.data")

        id = best_identified_speakers[0][0]
        score = best_identified_speakers[0][1]
        lname_voice = id.split('_')[2]
        fname_voice = id.split('_')[3]
        print('\n\n    VOICE RECOGNITION : '
            + '\n\t - Time to recognize voice : %f' % (end_rv) 
            + '\n\t - Identified the voice as : %s %s - (precision : %d%%)' % (lname_voice, fname_voice, int(100*score)))

    thread_voice = threading.Thread(target=verify_speaker)
    thread_voice.start()



    # ---------------------------------------
    #          Door Number Extraction
    # ---------------------------------------

    def extract_door_number():

        def word_to_num(s):
            numbers  = {'zero':'0', 'one':'1', 'two':'2', 'three':'3', 'four':'4', 
                        'five':'5', 'six':'6', 'seven':'7', 'eight':'8', 'nine':'9'}
            return numbers.get(s,"Not an integer")

        def words_to_digits(words_list):
            digits = ""
            for word in words_list:
                digits += word_to_num(word)
            if "Not an integer" in digits:
                return "One or more of the inputs is not an integer"
            return digits

        s2t_start = time.time()
        # Converting the .m4a input audio file to .wav (it will be deleted later on)
        os.system("ffmpeg -loglevel quiet -y -i " + audio_file_path + " audio_file.wav")
        conversion_end = time.time() - s2t_start
        os.system("deepspeech" 
                + " --model deepspeech_model.pbmm " 
                + " --scorer deepspeech_model.scorer " 
                + " --audio  audio_file.wav "
                + " > speech-to-text_result 2>&1")

        with open("speech-to-text_result", 'rt') as f:
            lines = f.readlines()

        # Deleting temp files
        os.system("rm speech-to-text_result")
        os.system("rm audio_file.wav")

        inference_time = lines[-2].replace("Inference took ", "").replace("\n", "")
        speech_full = lines[-1]
        door_number_words = speech_full.replace("\n", "").split(" ")[-4:]
        global door_number_digits
        door_number_digits = words_to_digits(door_number_words)

        print("\n\n    DOOR NUMBER EXTRACTION : "
            + "\n\t - Speech to text lasted : %f" % (time.time() - s2t_start)
            + "\n\t    + DeepSpeech inference took : %s" % inference_time
            + "\n\t    + Conversion (.m4a to .wav) took : %f" % conversion_end
            + "\n\t - Door number (words) : %s" % str(door_number_words)
            + "\n\t - Door number (digits) : %s" % door_number_digits)

    thread_speech2text = threading.Thread(target=extract_door_number)
    thread_speech2text.start()



    # -----------------------------------
    #              DECISION
    # -----------------------------------
    
    # Waiting for face thread execution to finish
    thread_face.join()
    
    # Checking if the face extraction returned any errors
    f = open("face_detect_err_file", "rt")
    err = f.read()
    f.close()
    os.system("rm face_detect_err_file")
    if (len(err) != 0):
        return "Visage non visible" if "face" in err else "Image introuvable"

    # Waiting for speech-to-text thread execution to finish
    thread_speech2text.join()

    # Waiting for voice thread execution to finish
    thread_voice.join()

# Always delete user data, for debugging purposes, remove this line for production & restore the one below
    #os.system("rm " + audio_file_path + " " + img_file_path + " " + img_file_path.replace(".jpg", "_visage.jpg"))
        
    # Retrieving threshold values from config file
    threshold_face = float(hp.integration.face_threshold)
    threshold_voice = float(hp.integration.voice_threshold)
    threshold_general = (threshold_face + threshold_voice)/2

    # Accessing recognition results from the modules
    top_face_id = best_identified_faces[0][0]
    top_voice_id = best_identified_speakers[0][0]

    # Accessing best candidates & calculating the dynamic decision function
    top_face_acc = best_identified_faces[0][1]
    top_voice_acc = best_identified_speakers[0][1]
    
    # Retrieving the importance weights for face & voice
    weight_face = hp.integration.weight_face
    weight_voice = hp.integration.weight_voice

    # Calculate the dynamic (general) accuracy using retrieved weights
    general_acc = round(weight_face*top_face_acc + weight_voice*top_voice_acc, 2)


    print("\n\n\n ==> DECISION : ")

    if (top_face_id == top_voice_id) and (top_face_acc >= threshold_face) \
                                     and (top_voice_acc >= threshold_voice) \
                                     and (general_acc >= threshold_general):

        # Delete user data when succeessfully identified
        #os.system("rm " + audio_file_path + " " + img_file_path + " " + img_file_path.replace(".jpg", "_visage.jpg"))
        
        # Check is the identified person has the access credentials
        def has_access(id, door):
            return (int(100*general_acc) % 2 == 0)   # dummy condition, just for variation

        # Check if the speech-to-text module successfuly extracted the door number 
        if ("integer" not in door_number_digits):

            if (has_access(id, door_number_digits)):
                # grant_access() # function to grant access (pings the hardware side of the system)
                print('\n\t - Access granted (door %s)' % door_number_digits)
                access_msg = ''
            else:
                print('\n\t - Access denied (door %s)' % door_number_digits)
                access_msg = ' Accès refusé'
        else:
            access_msg = ' Numéro porte inaudible'

        return_msg = 'Bienvenue, ' + ' '.join(best_identified_faces[0][0].split('_')[2:4]) + access_msg
        lname_rec = top_face_id.split('_')[2]
        fname_rec = top_face_id.split('_')[3]
        print('\n\t # Identity confirmed successfully, %s %s - (global precision : %d%%)' % (lname_rec, fname_rec, int(100*general_acc)))

    elif (top_face_acc < threshold_face) and (top_voice_acc < threshold_voice):
        return_msg = 'Non reconnu'
        print('\n\t - Not recognized')

    elif (top_face_acc < threshold_face):
        return_msg = 'Visage non reconnu, réessayez'
        print('\n\t - Face accuracy < threshold, waiting for retry...')

    elif (top_voice_acc < threshold_voice):
        return_msg = 'Voix non reconnue, réessayez'
        print('\n\t - Voice accuracy < threshold, waiting for retry...')

    elif (general_acc < threshold_general):
        return_msg = 'Non reconnu, réessayez'
        print('\n\t - Dynamic function not satistied, waiting for retry...')

    else: # (top_face_id != top_voice_id) even though both thresholds are satisfied
        return_msg = 'Partiellement reconnu, réessayez'
        print('\n\t - Face and voice mismatch, waiting for retry...')

    print("\n\t # Global recognition time : %f" % (time.time() - start_rec))

    print("\n\n\n\n\n    Ordered list of speakers : \n")
    print(*best_identified_speakers, sep='\n')
    print("\n    Ordered list of faces : \n")
    print(*best_identified_faces, sep='\n')


    print('\n\n\n\n\n\n')
    return return_msg



##################################################################################################################################
##################################################################################################################################
##################################################################################################################################
##################################################################################################################################
##################################################################################################################################



@app.route('/upload_enrollment', methods = [ 'POST'])
def upload_enroll():
    
    print('\n\n\n\n ########################### Incoming Enrollment ... ########################### \n')

    if not request.form['IMG'] \
    or not request.form['AUDIO'] \
    or not request.form['user-firstname'] \
    or not request.form['user-lastname'] \
    or not request.form['timestamp']:
        return 'Données non complètes'


    # Decrypting data
    img_data_encoded = aes_cipher.decrypt(request.form['IMG'])
    audio_data_encoded = aes_cipher.decrypt(request.form['AUDIO'])
    fname = aes_cipher.decrypt(request.form['user-firstname'])
    lname = aes_cipher.decrypt(request.form['user-lastname'])
    timestamp = aes_cipher.decrypt(request.form['timestamp'])

    # Decoding image and audio data
    img_data = base64.b64decode(img_data_encoded)
    audio_data = base64.b64decode(audio_data_encoded)

    user_id = timestamp + "_" + lname + "_" + fname

    # Writing image data to disk
    img_file_name = user_id + "_enroll_photo.jpg"
    img_file_path = hp.integration.enroll_upload_photo_folder + img_file_name
    with open(img_file_path, 'wb') as f:
        f.write(img_data)
    
    # Writing audio data to disk
    audio_file_name = user_id + "_enroll_audio.m4a"
    audio_file_path = hp.integration.enroll_upload_audio_folder + audio_file_name
    with open(audio_file_path, 'wb') as f:
        f.write(audio_data)

    # Extracting & saving voice embeddings
    start_rv = time.time()
    err_code_rv = os.system("conda run -n voice_py3 python -W ignore " 
                                + hp.integration.speaker_verification_path + "verify_speaker.py" 
                                + " --verify f " 
                                + " --test_wav_file " + audio_file_path)
    print("\t - Time to extract voice embeddings : %f" % (time.time() - start_rv))

    # Extracting & saving face 
    start_rf1 = time.time()
    err_code_rf1 = os.system("conda run -n pytorch_main python -W ignore " 
                                + hp.integration.face_verification_path + "extract_face.py" 
                                + " --input_image " + img_file_path 
                                + " --destination_dir " + hp.integration.enroll_upload_photo_folder)
    print("\t - Time to extract face : %f" % (time.time() - start_rf1))

    # Extracting & saving facea embeddings 
    start_rf1_1 = time.time()
    input_face_image = hp.integration.enroll_upload_photo_folder + img_file_name.replace(".jpg", "_visage.jpg")
    err_code_rf2 = os.system("conda run -n vgg_py3 python -W ignore " 
                                + hp.integration.face_verification_path + "save_face_embeddings.py"
                                + " --input_image " + input_face_image
                                + " --destination_dir " + hp.integration.enroll_preprocessed_photo)
    print("\t - Time to get and save face embeddings : %f" % (time.time() - start_rf1_1))

    # if (err_code_rf1 + err_code_rf2 == 0):
    #     os.system("rm " + img_file_path + " " + input_face_image)
    # audio_file_path = 'uploads_enrollment/audio/' + os.path.splitext(aes_cipher.decrypt(request.form['audio-file-name']))[0] + '.npy'
    # img_file_path = 'uploads_enrollment/photo/'+ os.path.splitext(aes_cipher.decrypt(request.form['photo-file-name']))[0] + '_visage.jpg'
    
    
    # insert new user into database
    insert_new_user(id_employee=user_id, first_name=fname, last_name= lname)
    
    print('\n\t     # Successfully enrolled : ' + lname + ' ' + fname)

    print('\n\t     # Photo and audio preprocessed and saved under the ID : ' + user_id + '\n')
    
    return 'Inscription réussie'


if __name__ == '__main__':
    #app.debug = True
    host, port = ("193.194.91.145", 5004)
    app.run(host=host, port= port, debug=True)
    """ create_empty_db()
    print('\n\tEmpty Data base created...') """

