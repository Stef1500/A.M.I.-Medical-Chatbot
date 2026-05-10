from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
from Bio import Entrez
import torch
import time
import os
import requests
import xml.etree.ElementTree as ET
from datetime import datetime


# =========================
# MODEL LOAD
# =========================

device = "cuda" if torch.cuda.is_available() else "cpu"

base_model = "unsloth/Llama-3.1-8B-Instruct-unsloth-bnb-4bit"
adapter_path = r"AMI_adapter" #rename the folder to AMI_adapter and place it inside a folder with app.y and ami_engine.py



Entrez.email = "lb16e@fsu.edu"
NCBI_TOOL = "AMI_Medical_Assistant"

tokenizer = AutoTokenizer.from_pretrained(base_model)
tokenizer.pad_token = tokenizer.eos_token

#Try using GPU, if not found, use CPU
try:
    model = AutoModelForCausalLM.from_pretrained(
        base_model,
        device_map={"": 0},
    )
except RuntimeError:
    print("NO GPU FOUND, USING CPU")
    model = AutoModelForCausalLM.from_pretrained(
        base_model,
        device_map={"": "cpu"},
    )

model = PeftModel.from_pretrained(model, adapter_path)
model.eval()


# =========================
# HELPERS
# =========================

def parse_pub_date(pub_date):
    if "Year" in pub_date:
        year = str(pub_date["Year"])
        month = str(pub_date.get("Month", "01"))
        day = str(pub_date.get("Day", "01"))
        return f"{year}-{month}-{day}"
    if "MedlineDate" in pub_date:
        return str(pub_date["MedlineDate"])
    return "n.d."


def current_year():
    return str(datetime.now().year)


def normalize_whitespace(text):
    return " ".join(str(text).split()).strip()


def is_emergency(user_input):
    q = user_input.lower()
    red_flags = [
        "chest pain",
        "trouble breathing",
        "can't breathe",
        "cannot breathe",
        "shortness of breath",
        "stroke",
        "slurred speech",
        "suicidal",
        "overdose",
        "passed out",
        "fainted",
        "severe allergic reaction",
        "anaphylaxis",
        "seizure",
        "blue lips",
        "confused and fever",
    ]
    return any(flag in q for flag in red_flags)


def classify_query(user_input):
    q = user_input.lower().strip()

    emergency_terms = [
        "chest pain",
        "trouble breathing",
        "can't breathe",
        "cannot breathe",
        "shortness of breath",
        "stroke",
        "slurred speech",
        "suicidal",
        "overdose",
        "anaphylaxis",
        "severe allergic reaction",
        "passed out",
        "fainted",
    ]
    if any(term in q for term in emergency_terms):
        return "emergency"

    small_talk_terms = [
        "hi", "hello", "hey", "how are you", "what's up", "whats up",
        "good morning", "good afternoon", "good evening", "thanks", "thank you",
        "who are you", "what is your name", "bye", "goodbye"
    ]
    if q in small_talk_terms:
        return "small_talk"

    for term in small_talk_terms:
        if q.startswith(term) and len(q.split()) <= 6:
            return "small_talk"

    common_medical_terms = [
        "sore throat", "headache", "mild headache", "cough", "runny nose",
        "cold", "fever", "dehydration", "nausea", "vomiting", "diarrhea",
        "fatigue", "congestion", "stuffy nose", "body aches", "scratchy throat",
        "what can i do", "what helps", "home remedy", "make it better"
    ]
    if any(term in q for term in common_medical_terms):
        return "common_medical_info"

    medical_terms = [
        "pain", "hurt", "symptom", "symptoms", "treatment", "medicine",
        "medication", "doctor", "hospital", "infection", "virus", "condition",
        "rash", "allergy", "swelling", "dose", "medical", "health",
        "diagnose", "disease", "injury", "migraine", "stomach"
    ]
    if any(term in q for term in medical_terms):
        return "research_heavy_medical"

    return "unclear"


def determine_presentation_state(query_type, user_input):
    if query_type == "small_talk":
        return {
            "expression_state": "friendly",
            "severity": "none",
            "thinking_state": "done",
        }

    if query_type == "common_medical_info":
        return {
            "expression_state": "supportive",
            "severity": "low",
            "thinking_state": "done",
        }

    if query_type == "research_heavy_medical":
        return {
            "expression_state": "serious",
            "severity": "medium",
            "thinking_state": "done",
        }

    if query_type == "emergency":
        return {
            "expression_state": "urgent",
            "severity": "high",
            "thinking_state": "urgent_flagged",
        }

    return {
        "expression_state": "neutral",
        "severity": "low",
        "thinking_state": "done",
    }


# =========================
# RETRIEVAL
# =========================

def search_pubmed(user_input, retmax=2):
    results = []
    try:
        handle = Entrez.esearch(
            db="pubmed",
            term=user_input,
            retmax=retmax,
            sort="relevance",
            tool=NCBI_TOOL,
            email=Entrez.email,
        )
        search_record = Entrez.read(handle)
        handle.close()

        id_list = search_record.get("IdList", [])

        for pmid in id_list:
            fetch_handle = Entrez.efetch(
                db="pubmed",
                id=pmid,
                retmode="xml",
                tool=NCBI_TOOL,
                email=Entrez.email,
            )
            fetched_records = Entrez.read(fetch_handle)
            fetch_handle.close()

            for pubmed_record in fetched_records.get("PubmedArticle", []):
                article = pubmed_record["MedlineCitation"]["Article"]

                title = normalize_whitespace(article.get("ArticleTitle", "Title Not Available"))

                if "Abstract" in article and "AbstractText" in article["Abstract"]:
                    abstract = " ".join(normalize_whitespace(x) for x in article["Abstract"]["AbstractText"])
                else:
                    abstract = "Abstract not available."

                authors = []
                for a in article.get("AuthorList", []):
                    full_name = f"{a.get('ForeName', '')} {a.get('LastName', '')}".strip()
                    if full_name:
                        authors.append(full_name)

                journal = normalize_whitespace(article["Journal"].get("Title", "Journal Not Available"))
                pub_date = parse_pub_date(article["Journal"]["JournalIssue"]["PubDate"])
                url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

                results.append({
                    "source_type": "PubMed",
                    "title": title,
                    "snippet": abstract,
                    "authors": authors if authors else ["Authors Not Available"],
                    "container": journal,
                    "year": pub_date[:4] if pub_date and pub_date[:4].isdigit() else "n.d.",
                    "date": pub_date,
                    "url": url,
                    "publisher": "National Library of Medicine",
                    "priority": 3,
                })

            time.sleep(0.34)

    except Exception as e:
        print(f"[PubMed retrieval error] {e}")

    return results


def search_cdc(user_input, max_results=2):
    results = []
    try:
        url = "https://tools.cdc.gov/api/v2/resources/media"
        params = {
            "topic": user_input,
            "max": max_results,
        }

        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        payload = resp.json()

        items = payload.get("results", []) if isinstance(payload, dict) else []
        for item in items[:max_results]:
            title = normalize_whitespace(item.get("name", ""))
            desc = normalize_whitespace(item.get("description", ""))
            page_url = item.get("url", "")
            date_published = item.get("datePublished", "") or item.get("dateModified", "")
            year = date_published[:4] if date_published[:4].isdigit() else current_year()

            if not title and not desc:
                continue

            results.append({
                "source_type": "CDC",
                "title": title or "CDC resource",
                "snippet": desc or "No summary available.",
                "authors": ["Centers for Disease Control and Prevention"],
                "container": "CDC",
                "year": year,
                "date": date_published or "n.d.",
                "url": page_url,
                "publisher": "Centers for Disease Control and Prevention",
                "priority": 2,
            })

    except Exception as e:
        print(f"[CDC retrieval error] {e}")

    return results


def search_medlineplus(user_input, retmax=3):
    results = []
    try:
        url = "https://wsearch.nlm.nih.gov/ws/query"
        params = {
            "db": "healthTopics",
            "term": user_input,
            "retmax": retmax,
            "tool": NCBI_TOOL,
            "email": Entrez.email,
        }

        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()

        root = ET.fromstring(resp.text)

        for docsum in root.findall(".//document")[:retmax]:
            title = ""
            snippet = ""
            page_url = ""
            group_name = "MedlinePlus"

            for content in docsum.findall("content"):
                name = content.attrib.get("name", "")
                value = normalize_whitespace(content.text or "")
                if name == "title":
                    title = value
                elif name == "FullSummary":
                    snippet = value
                elif name == "url":
                    page_url = value
                elif name == "groupName":
                    group_name = value

            if not title:
                continue

            results.append({
                "source_type": "NIH",
                "title": title,
                "snippet": snippet or "No summary available.",
                "authors": ["National Library of Medicine"],
                "container": group_name or "MedlinePlus",
                "year": current_year(),
                "date": current_year(),
                "url": page_url,
                "publisher": "National Library of Medicine",
                "priority": 1,
            })

    except Exception as e:
        print(f"[MedlinePlus retrieval error] {e}")

    return results


def dedupe_sources(sources):
    seen = set()
    deduped = []
    for src in sources:
        key = (src.get("url", ""), src.get("title", ""))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(src)
    return deduped


def filter_sources_for_question(user_input, sources):
    q = user_input.lower()

    blocked_for_common = [
        "hiv", "myocardial infarction", "stroke", "cancer", "sepsis",
        "thrombosis", "heart attack", "cryptosporidiosis",
        "infectious mononucleosis", "mononucleosis"
    ]

    common_triggers = [
        "sore throat", "headache", "dehydration", "cough", "cold",
        "runny nose", "nausea", "vomiting", "diarrhea"
    ]

    if any(term in q for term in common_triggers):
        filtered = []
        for src in sources:
            text = f"{src.get('title', '')} {src.get('snippet', '')}".lower()
            if any(term in text for term in blocked_for_common):
                continue
            filtered.append(src)
        return filtered

    return sources


def rank_sources(sources, query_type):
    if query_type == "common_medical_info":
        source_order = {"NIH": 0, "CDC": 1, "PubMed": 2}
    elif query_type == "research_heavy_medical":
        source_order = {"PubMed": 0, "NIH": 1, "CDC": 2}
    else:
        source_order = {"NIH": 0, "CDC": 1, "PubMed": 2}

    return sorted(
        sources,
        key=lambda s: (
            source_order.get(s.get("source_type", ""), 9),
            s.get("priority", 9),
        ),
    )


def retrieve_sources(user_input, query_type):
    sources = []

    if query_type == "common_medical_info":
        sources.extend(search_medlineplus(user_input, retmax=3))
        sources.extend(search_cdc(user_input, max_results=2))
        sources.extend(search_pubmed(user_input, retmax=1))

    elif query_type == "research_heavy_medical":
        sources.extend(search_pubmed(user_input, retmax=3))
        sources.extend(search_medlineplus(user_input, retmax=2))
        sources.extend(search_cdc(user_input, max_results=2))

    elif query_type == "unclear":
        sources.extend(search_medlineplus(user_input, retmax=2))
        sources.extend(search_cdc(user_input, max_results=1))

    sources = dedupe_sources(sources)
    sources = filter_sources_for_question(user_input, sources)
    sources = rank_sources(sources, query_type)
    return sources[:5]


def build_evidence_block(sources):
    if not sources:
        return "No external evidence was retrieved."

    evidence_parts = []
    for i, src in enumerate(sources, start=1):
        evidence_parts.append(
            f"""[{i}]
Source Type: {src['source_type']}
Title: {src['title']}
Authors/Organization: {", ".join(src['authors'])}
Container: {src['container']}
Date: {src['date']}
URL: {src['url']}
Snippet: {src['snippet']}
"""
        )
    return "\n".join(evidence_parts)


def references_for_frontend(sources):
    refs = []
    for i, src in enumerate(sources, start=1):
        refs.append({
            "label": f"[{i}]",
            "title": src.get("title", "Untitled"),
            "url": src.get("url", ""),
            "source_type": src.get("source_type", ""),
            "container": src.get("container", ""),
            "year": src.get("year", "n.d.")
        })
    return refs


# =========================
# CHAT HISTORY CONVERSION
# =========================

def convert_prior_messages_to_chat_history(prior_messages):
    """
    Convert DB messages into chat-template history.
    Keeps only recent turns.
    """
    chat_history = []

    for msg in prior_messages[-12:]:
        sender = msg.get("sender", "user")
        text = msg.get("text", "").strip()

        if not text:
            continue

        role = "assistant" if sender == "ai" else "user"
        chat_history.append({
            "role": role,
            "content": text
        })

    return chat_history


# =========================
# MAIN GENERATION FUNCTION
# =========================

def generate_ami_reply(user_input, prior_messages):
    query_type = classify_query(user_input)
    presentation = determine_presentation_state(query_type, user_input)

    if query_type == "emergency" or is_emergency(user_input):
        return {
            "reply": (
                "I’m not allowed to diagnose anything, but those symptoms could be serious. "
                "Please seek urgent medical care or call emergency services right away."
            ),
            "query_type": "emergency",
            "expression_state": "urgent",
            "thinking_state": "urgent_flagged",
            "severity": "high",
            "references": []
        }

    sources = []
    evidence_block = "No external evidence was retrieved."

    if query_type in ["common_medical_info", "research_heavy_medical", "unclear"]:
        sources = retrieve_sources(user_input, query_type)
        evidence_block = build_evidence_block(sources)

    chat_history = convert_prior_messages_to_chat_history(prior_messages)

    try:
        user_preferences = os.environ["PREFERENCES"]
        preferences_set = True
        print(f"current references: {user_preferences}")
    except KeyError:
        print("no preferences set")
        preferences_set = False

    if preferences_set:
        print("applying preferences to prompt contraints")
        formatted_input = f"""
        for the entire conversation, you will follow these rules no matter what:
        1. you are a virtual medical assistant named AMI (Artificial Medical Intelligence).
        2. do not keep re-introducing yourself unless the user asks who you are.
        3. you have a friendly personality that makes the user experience when conversing with you comfortable.
        4. when you use an external source for any part of your response, use inline citations like [1], [2], [3].
        5. if no external source was actually retrieved, do not invent, guess, or fabricate citations or references.
        6. you are NOT allowed to diagnose anything.
        7. only include emergency or escalation warnings when they are relevant to the user's question.
        8. do not jump to severe, rare, or life-threatening conditions unless the user describes red-flag symptoms or the retrieved evidence clearly requires that concern.
        9. for common symptom questions, prioritize simple general self-care guidance before more complex discussion.
        10. make sure to let the user know that if they think they really need help they should consult a medical professional.
        11. only answer the question asked and do not add unrelated medical speculation.
        12. use only the evidence provided below for factual medical claims.
        13. if the evidence is insufficient, clearly say so.
        14. if the user is only greeting you or making small talk, respond naturally and do not use citations.
        15. do not write a references section yourself. only use inline citations.


        query type:
        {query_type}

        user question:
        {user_input}
        
        user preferences, MAKE SURE to follow this instructions:
        {user_preferences}

        retrieved evidence:
        {evidence_block}
        """
    else:
        print("applying normal prompt constraints")
        formatted_input = f"""
        for the entire conversation, you will follow these rules no matter what:
        1. you are a virtual medical assistant named AMI (Artificial Medical Intelligence).
        2. do not keep re-introducing yourself unless the user asks who you are.
        3. you have a friendly personality that makes the user experience when conversing with you comfortable.
        4. when you use an external source for any part of your response, use inline citations like [1], [2], [3].
        5. if no external source was actually retrieved, do not invent, guess, or fabricate citations or references.
        6. you are NOT allowed to diagnose anything.
        7. only include emergency or escalation warnings when they are relevant to the user's question.
        8. do not jump to severe, rare, or life-threatening conditions unless the user describes red-flag symptoms or the retrieved evidence clearly requires that concern.
        9. for common symptom questions, prioritize simple general self-care guidance before more complex discussion.
        10. make sure to let the user know that if they think they really need help they should consult a medical professional.
        11. only answer the question asked and do not add unrelated medical speculation.
        12. use only the evidence provided below for factual medical claims.
        13. if the evidence is insufficient, clearly say so.
        14. if the user is only greeting you or making small talk, respond naturally and do not use citations.
        15. do not write a references section yourself. only use inline citations.


        query type:
        {query_type}

        user question:
        {user_input}

        retrieved evidence:
        {evidence_block}
        """

    chat_history.append({"role": "user", "content": formatted_input})
    chat_history = chat_history[-15:]

    inputs = tokenizer.apply_chat_template(
        chat_history,
        tokenize=True,
        add_generation_prompt=True,
        return_tensors="pt",
        return_dict=True,
    ).to(device)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=260,
            temperature=0.5,
            top_p=0.9,
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id
        )

    input_length = inputs["input_ids"].shape[1]
    new_tokens = outputs[0][input_length:]
    assistant_reply = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()

    return {
        "reply": assistant_reply,
        "query_type": query_type,
        "expression_state": presentation["expression_state"],
        "thinking_state": presentation["thinking_state"],
        "severity": presentation["severity"],
        "references": references_for_frontend(sources)
    }