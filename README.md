# BOLDigger
![](boldigger/data/logo.png)

Python program to query .fasta files against different databases of www.boldsystems.org

## Introduction
DNA-Metabarcoding often produces large numbers of OTUs which need to be queried against databases to identify the sequence. BOLD Systems offers such a database and is therefore used by many biologists. Unfortunately only a batch of 100 sequences can be identified in one run. Using the API does not solve the problem completly since it does not give access to the private and early release data. BOLDigger aims to solve this problem. As a pure python program with a user-friendly GUI it not only gives automated access to the identification engine but can also be used to download additional data for each sequence as well as helping to chose the top hit from the returned results. 

## Installation

## Login to your account

## Use the BOLD identification engine for COI, ITS and rbcL & matK

Once logged into the account the identification engine of BOLD can be used. An output folder needs to be selected where the results will be saved, as well as an input file in the .fasta format. Three different databases can be selected: **COI, ITS or rbcL & matK** as well as a **batch size**. This handles how many sequences will be identified in one request. 100 is the maximum value as well as the default for COI. Batch size depends on variuos parameters like your internet connection, availability of the BOLD database as well as  length of the requested sequences and needs to be adjusted when a lot of ConnectionError occour. 
A batch size of **100 is recommended for COI**, **10 for ITS**, and **< 5 for rbcL & matK.**
The results will be written to the output folder and will always be named "BOLDResults_fastaname.xlsx". In case a workbook with that name already exists in the output folder the results will be appended to this file. 
After every batch the requested sequences will be removed from the input file and written to a new file named "fastaname_done.fasta" in the same folder as the input file. This is to prevent running input files twice: If BOLDigger crashes it can just be restarted with the same output folder and input file and will continue right were the crash occured.

## Download additional data from BOLD

## Find the best fitting hit from the top 20 (COI) and top 99 (ITS / rbcL & matK)
