import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import re
from fuzzywuzzy import fuzz
from nltk.corpus import stopwords
import os
import time


try:
    stop_words = set(stopwords.words('english'))
except:
    stop_words = set()


def preprocess_text(text):
    text = text.lower()
    # text = re.sub(r'[,.-]', '', text)
    # text = re.sub(r'\b\d+\b|\bml\b', '', text)
    return text.strip()

def write_visited_log(url):
    with open(f'Visited_vwr_product_names.txt', 'a', encoding='utf-8') as file:
        file.write(f'{url}\n')

def read_log_file():
    if os.path.exists(f'Visited_vwr_product_names.txt'):
        with open(f'Visited_vwr_product_names.txt', 'r', encoding='utf-8') as read_file:
            return read_file.read().split('\n')
    return []


def tokenized_text(text):
    return [word for word in preprocess_text(text).split() if word not in stop_words]


def combined_similarity(title_1, title_2, vectorizer, title_1_vec):
    title_1_processed = preprocess_text(title_1)
    title_2_processed = preprocess_text(title_2)
    title_1_tokens = tokenized_text(title_1)
    title_2_tokens = tokenized_text(title_2)
    matching_words = set(title_1_tokens) & set(title_2_tokens)
    token_similarity_score = len(matching_words) / max(len(title_1_tokens), len(title_2_tokens))

    if not title_2_processed:
        return 0

    title_2_vec = vectorizer.transform([title_2_processed])
    tfidf_cosine = cosine_similarity(title_1_vec, title_2_vec)[0][0]

    sort_ratio = fuzz.token_sort_ratio(title_1_processed, title_2_processed) / 100
    set_ratio = fuzz.token_set_ratio(title_1_processed, title_2_processed) / 100

    combined_score = (token_similarity_score * 0.2) + (tfidf_cosine * 0.4) + (sort_ratio * 0.2) + (set_ratio * 0.2)
    return combined_score

def find_best_match(flinn_desc, dataset, product_name_col, vectorizer, title_1_vec):
    highest_similarity = 0.36
    best_match = None
    for _, row in dataset.iterrows():
        product_name = row.get(product_name_col, '')
        product_desc = product_name.lower() if pd.notna(product_name) else ''
        flinn_replace = flinn_desc.replace('flinn scientific', '').replace('flinn', '')
        similarity = combined_similarity(flinn_replace, product_desc, vectorizer, title_1_vec)
        if similarity > highest_similarity:
            print(f'{flinn_desc}-----------------{similarity}----------------{product_desc}')
            highest_similarity = similarity
            row['matching_percent'] = highest_similarity
            best_match = row.to_dict()
    return highest_similarity, best_match

def process_datasets(flinn_csv, vwr_csv):
    combined_matches = []

    for _, flinn_row in flinn_csv.iterrows():
        flinn_names = flinn_row['Flinn_product_name']
        if flinn_names in read_log_file():
            continue
        if pd.notna(flinn_names):
            flinn_desc = flinn_names.lower()
            print(f"Original: {flinn_desc}")

            if re.search('^\d"\sx\s\d"', str(flinn_names)):
                best_match = {
                    **flinn_row.to_dict(),
                    **{col: '' for col in vwr_csv.columns}
                }
                combined_df = pd.DataFrame([best_match])
                if os.path.isfile(f'vwr_master_file.csv'):
                    combined_df.to_csv(f'vwr_master_file.csv', index=False, header=False, mode='a')
                else:
                    combined_df.to_csv(f'vwr_master_file.csv', index=False)
                write_visited_log(flinn_names)
                continue

            flinn_processed = preprocess_text(flinn_desc)
            if flinn_processed:
                try:
                    vectorizer = TfidfVectorizer().fit([flinn_processed])
                    title_1_vec = vectorizer.transform([flinn_processed])

                    best_match_vwr = find_best_match(flinn_desc, vwr_csv, 'VWR_product_name', vectorizer, title_1_vec)[1]
                    best_match = {
                        **flinn_row.to_dict(),
                        **(best_match_vwr or {col: '' for col in vwr_csv.columns})
                    }
                    write_visited_log(flinn_names)
                    combined_df = pd.DataFrame([best_match])
                    if os.path.isfile(f'vwr_master_file.csv'):
                        combined_df.to_csv(f'vwr_master_file.csv', index=False, header=False, mode='a')
                    else:
                        combined_df.to_csv(f'vwr_master_file.csv', index=False)
                except ValueError as e:
                    print(f"Error processing '{flinn_desc}': {e}")
            else:
                print(f"Skipping '{flinn_desc}' due to empty processed text")

if __name__ == '__main__':
    start_time = time.time()
    flinn_csv = pd.read_csv('Flinn_Products.csv')
    vwr_csv = pd.read_csv('VWR_WARDS_Products.csv')
    process_datasets(flinn_csv, vwr_csv)
    print(f"Processing time: {time.time() - start_time} seconds")
