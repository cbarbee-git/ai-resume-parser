from dotenv import load_dotenv
### Load the .env file
load_dotenv()

import os
import json
import time
import PyPDF2
from collections.abc import Iterable
import pandas as pd
import openai
import google.generativeai as genai

# Set the directory containing the resumes, default of non-exist in .env
pdf_directory = os.environ.get('FOLDER_DIR', 'resumes') + '/'

#Define the AI prompt here:
prompt = """
    You are a resume parsing assistant. Given the following resume text, extract all the important details and return them in a well-structured JSON format.

    The resume text:
    {}

    Extract and include the following:
    - Name
    - Email Address
    - Degrees
    - University attended
    - Work Title
    - Employer
    - Years of Experience
    - Specialty Area.

    Return the response in JSON format.
"""

#Tell the script which AI to call to (change this variable to decide Google OR ChatGPT)
AImodel = os.environ.get('AImodel', 'google') # "google" OR "openai" 

#This variable will add a delay in batches of 10 resumes to prevent overwhemling AI Models
delay_in_seconds = os.environ.get('BATCH_DELAY_IN_SECONDS', 2)

if (AImodel == 'google' or AImodel == 'openai'):
    # Set your API keys from .env
    if(AImodel == 'google'):
        if(os.get('GOOGLE_API_KEY') is not None):
            genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
        else:
             quit("GOOGLE_API_KEY could not be found. Check '.env' file, or use another model.")
    if(AImodel == 'openai'):
        if(os.get('OpenAI_KEY') is not None):
             openai.api_key = os.getenv('OpenAI_KEY') 
        else:
            quit("OpenAI_KEY could not be found. Check '.env' file, or use another model.")
         
else:
    quit("AI Model variable not set. Unable to continue.")

def parse_resume_with_generativeai(resume,prompt,filename):
    # Prompt with detailed request from parsed text from PDF file
    prompt = prompt.format(resume)
    
    # load model
    model = genai.GenerativeModel("models/gemini-1.5-pro")

    # Generate response from the model
    try:
        response = model.generate_content(prompt).text
    except Exception as e:
        response = "{'Name': '*** UNABLE TO PROCESS - " + filename + " ***'}"
    return response
    
def parse_resume_with_chatgpt(resume,prompt,filename):
    # Prompt with detailed request
    prompt.format(resume)

     # Generate response from the model
    try:
        response = openai.Completion.create(
            engine="gpt-3.5-turbo",
            prompt=prompt,
            max_tokens=500,
            temperature=0.5
        )
        return response.choices[0].text.strip()
    except Exception as e:
        response = "{'Name': '*** UNABLE TO PROCESS - " + filename + " ***'}"
        return response

# Define a function to extract text from a PDF
def extract_text_from_pdf(pdf_path):
    with open(pdf_path, 'rb') as file:
        reader = PyPDF2.PdfReader(file)
        text = ''
        for page in reader.pages:
            text += page.extract_text()
    return text

# Function to process multiple PDF files
def process_resumes(pdf_dir):
    resumes_data = []
    count = 0
    for filename in os.listdir(pdf_dir):
        if filename.endswith('.pdf'):
            #batch 10 resumes, then add delay to not cause timeout
            if (count % 10 == 0): 
                # Add a delay of X seconds, defined above
                time.sleep(delay_in_seconds)

            pdf_path = os.path.join(pdf_dir, filename)
            print(f"Processing {filename}...")
            text = extract_text_from_pdf(pdf_path)
            if(text != ''):
                # Get resume details from the model
                if (AImodel == 'google' or AImodel == 'openai'):
                    # Set your API keys from .env
                    if(AImodel == 'google'):
                       response = parse_resume_with_generativeai(text, prompt, filename)
                    if(AImodel == 'openai'):
                       response = parse_resume_with_chatgpt(text, prompt, filename)   
                else:
                    quit("AI Model variable not set. Unable to continue.")
                                
                # Clean the response by removing the ```json and surrounding text
                response_clean = response.replace("```json", "").replace("```", "").strip()
                # Load the cleaned response into a dictionary
                try:
                    data = json.loads(response_clean)
                except:
                    details = add_empty_row(filename)
                
                # Extract details from the JSON response
                full_name = case_insensitive_get(data,"Name","")
                email_address = case_insensitive_get(data,"Email Address","")
                degrees = data.get("Degree", [])
                degrees_str = join_or_string(degrees)
                universities = data.get("University attended", [])
                universities_str = join_or_string(universities)
                work_title = data.get("Work Title", [])
                work_title_str = join_or_string(work_title)
                employer = data.get("Employer", [])
                employer_str = join_or_string(employer)
                years_of_experience = data.get("Years of Experience", "")
                specialty_area = data.get("Specialty Area", [])
                specialty_area_str = join_or_string(specialty_area)
                #Check if we can interpret what was returned, if NOT check these keys instead
                if ( not email_address ):
                    full_name = case_insensitive_get(data,"name","")
                    email_address = case_insensitive_get(data,"email","")
                    degrees = data.get("degrees", [])
                    degrees_str = join_or_string(degrees)
                    universities = data.get("university", [])
                    universities_str = join_or_string(universities)
                    work_title = data.get("title", [])
                    work_title_str = join_or_string(work_title)
                    employer = data.get("employer", [])
                    employer_str = join_or_string(employer)
                    years_of_experience = data.get("total_years_of_experience", "")
                    specialty_area = data.get("specialty_area", [])
                    specialty_area_str = join_or_string(specialty_area)
                    #Still unable to interpret the response data. Add this row to be fixed manually
                    if(email_address is None) :
                        details = add_empty_row(filename)
                    else :
                        #Keys have value, add the row with the returned values
                        details = {
                            'Name': full_name,  
                            'Email': email_address,
                            'Degrees': degrees_str,
                            'University Attended': universities_str,
                            'Work Title': work_title_str,
                            'Employer': employer_str,
                            'Years of Experience': years_of_experience,
                            'Specialty Area': specialty_area_str,
                            'File': filename
                        }
            else:
                #No text response was sent from the server, Add this row to be fixed manually
                details = add_empty_row(filename)
                
            # Add details to the Data to return
            resumes_data.append(details)
            count += 1
            print(f"Completed {filename}...")
            
        
    return pd.DataFrame(resumes_data)

def add_empty_row(filename):
    #add a row with filename but no data
    details = {
        'Name': '*** UNABLE TO PROCESS - ' + filename + ' ***',  
        'Email': 'N/A',
        'Degrees': 'N/A',
        'University Attended': 'N/A',
        'Work Title': 'N/A',
        'Employer': 'N/A',
        'Years of Experience': 'N/A',
        'Specialty Area': 'N/A',
        'File': filename
    }
    return details


def join_or_string(iterable_in, separator="\n"):
    if isinstance(iterable_in, str):
        return iterable_in  
    else:
        if isinstance(iterable_in, dict):
                for key, value in iterable_in.items():
                    result = separator.join(iterable_in.values())
                return result
        else:
            if isinstance(iterable_in, Iterable):
                try:
                    result = separator.join(iterable_in)
                except Exception:
                    result = '*** Failed to Extract ***'
                    #continue
                return result
            else:
                return iterable_in

def case_insensitive_get(data, key, default=None):
    for k in data.keys():
        if k.lower() == key.lower():
            return data[k]
    return default

# Extract data and convert it into a DataFrame
resume_df = process_resumes(pdf_directory)

# Save the results to a CSV file
extracted_data_file_name = os.environ.get('EXTRACTED_DATA_FILENAME', 'resumes_extracted_data.csv')
resume_df.to_csv(extracted_data_file_name, index=False)
print("Data extraction complete. Results saved to '{extracted_data_file_name}'.").format(extracted_data_file_name)