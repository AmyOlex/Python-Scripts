#!/usr/bin/python

#############
# Amy Olex @ CCTR
# 8/25/2014
#
# Purpose: This Python script takes as input an XML file that was generated by GeneTorrents cgquery program.
# It parses the XML file to extract the meta analysis information out into a tab-delimited file for easy reading.
# Meta analysis information includes the reference genome used for alignement, the alignment software such as BWA,
# and any other processing tools such as samtools that were used to obtain the final BAM files.  This script also
# parses out whether or not the BAM file contains unmapped reads, if it marks duplicates and if in includes failed reads.
# 
# UPDATED: 9/15/14
# Specilazation:  This script was modified from the above to parse out ALL clinical fields from the TCGA XML Clinical files.
# The strategy is to put those with the same namespace together.
# 
# UPDATED: 2/2/2016
# Updated line 54 so that is is no longer specific to the xml schema version used by TCGA.  Further updates on XML schema should nolonger break this script.
###############




# Import modules
import sys, getopt
import subprocess, shlex, shutil
import os, glob
import xml.etree.ElementTree as ET
import re



def parse_and_get_ns(file):
   events = "start", "start-ns"
   root = None
   ns = {}
   for event, elem in ET.iterparse(file, events):
     if event == "start-ns":
       if elem[0] in ns and ns[elem[0]] != elem[1]:
         # NOTE: It is perfectly valid to have the same prefix refer
         #     to different URI namespaces in different parts of the
         #     document. This exception serves as a reminder that this
         #     solution is not robust.    Use at your own peril.
         raise KeyError("Duplicate prefix with different URI found.")
       ns[elem[0]] = "{%s}" % elem[1]
     elif event == "start":
       if root is None:
         root = elem
   return ET.ElementTree(root), ns


def parse_tag(tag):
   mo = re.match("{http://tcga.nci/bcr/xml/clinical/(.*/).*}(.*)", tag)
   new_tag = ''.join(mo.groups()) if mo is not None else ''
   return new_tag



# Add 1,2,3,etc to drugs, followups and NTEs and look for others.
# remove tabs between recursive steps

# Elem is a list of xml node objects
def parse_xml_tree_recursive(elem, header, content, parent_tag, flag):
   header_return = header
   content_return = content
   
   if parent_tag == 'coad/follow_ups':
      f = 0
      for e in elem:
         f = f+1
         new_flag = 'FollowupSeq_' + str(f)
         e_list = e.getiterator()
         #print e.tag + ":\t" + str(len(e_list))

         if len(e_list)>1:
            #print "Recursive call here"
            e_child = e.getchildren()
            #print str(len(e_child))
            header_return, content_return = parse_xml_tree_recursive(e_child, header_return, content_return, parse_tag(e.tag), new_flag)

      # end for e in elem
      return header_return, content_return
      
   elif parent_tag == 'pharmaceutical/drugs':
      f = 0
      for e in elem:
         f = f+1
         new_flag = 'DrugSeq_' + str(f)
         e_list = e.getiterator()
         #print e.tag + ":\t" + str(len(e_list))

         if len(e_list)>1:
            #print "Recursive call here"
            e_child = e.getchildren()
            #print str(len(e_child))
            header_return, content_return = parse_xml_tree_recursive(e_child, header_return, content_return, parse_tag(e.tag), new_flag)

      # end for e in elem
      return header_return, content_return

   elif parent_tag == 'radiation/radiations':
      f = 0
      for e in elem:
         f = f+1
         new_flag = 'RadSeq_' + str(f)
         e_list = e.getiterator()
         #print e.tag + ":\t" + str(len(e_list))

         if len(e_list)>1:
            #print "Recursive call here"
            e_child = e.getchildren()
            #print str(len(e_child))
            header_return, content_return = parse_xml_tree_recursive(e_child, header_return, content_return, parse_tag(e.tag), new_flag)

      # end for e in elem
      return header_return, content_return
      
   else:
   
      for e in elem:
         e_list = e.getiterator()
         #print e.tag + ":\t" + str(len(e_list))

         if len(e_list)>1:
            #print "Recursive call here"
            e_child = e.getchildren()
            #print str(len(e_child))
            header_return, content_return = parse_xml_tree_recursive(e_child, header_return, content_return, parse_tag(e.tag), flag)
         else:
            if flag != 0:
               try:
                  header_return = header_return + "\t" + str(flag) + "/" + parse_tag(e.tag)
                  c = e.text if e.attrib['procurement_status']=='Completed' else e.attrib['procurement_status']
                  content_return = content_return + "\t" + c
                  #print e.tag + ":" + c
               except KeyError:
                  header_return = header_return + "\t" + str(flag) + "/" + arse_tag(e.tag)
                  content_return = content_return + "\tField not avaliable"
            else:
               try:
                  c = e.text if e.attrib['procurement_status']=='Completed' else e.attrib['procurement_status']
                  content_return = content_return + "\t" + c
                  header_return = header_return + "\t" + parse_tag(e.tag)
                  #print e.tag + ":" + c
               except KeyError:
                  print "KeyError: " + parse_tag(e.tag)
                  #header_return = header_return + "\t" + parse_tag(e.tag)
                  #content_return = content_return + "\tField not avaliable"
      # end for e in elem
      return header_return, content_return



# 3 spaces indent for main method
def main(argv):
   
   # Parse input arguments
   try:
      opts, args = getopt.getopt(argv,"hi:o:d:",["idir=","ofile=", "odir="])
   except getopt.GetoptError:
      print 'TCGA_parseMetadata.py -i <inputdirectory> -o <outputfile>'
      sys.exit(2)
   for opt, arg in opts:
      if opt == '-h':
         print 'TCGA_parseMetadata.py -i <inputdirectory> -o <outputfile>'
         sys.exit()
      elif opt in ("-i", "--idir"):
         inputdirectory = arg
      elif opt in ("-o", "--ofile"):
         outputfile = arg
      elif opt in ("-d", "--odir"):
         outputdir = arg

   print 'Input directory is ' + inputdirectory
   print 'Output file is ' + outputfile
   print 'Output directory is ' + outputdir

   # Get list of XML files to process
   findcommand = "find %s -iname *clinical.TCGA-*.xml"%(inputdirectory)
   proc = subprocess.Popen(findcommand, shell=True, stdout=subprocess.PIPE)
   files = proc.communicate()[0]
   filelist = files.rstrip().lstrip().split("\n")
   print "Parsing %i files."%(len(filelist))


   # Open the output file
   #out = open(outputfile, "w")
   #out.write('Barcode\tdays_to_initial_pathologic_diagnosis\tdays_to_death\tdays_to_birth\tdays_to_last_known_alive\tfollowup_sequence\tvital_status\tdays_to_last_followup\tdays_to_death\tperson_neoplasm_cancer_status\tnew_tumor_event_after_initial_treatment\tdays_to_new_tumor_event_after_initial_treatment\tfollowup_treatment_success\tfollowup_sequence\tvital_status\tdays_to_last_followup\tdays_to_death\tperson_neoplasm_cancer_status\tnew_tumor_event_after_initial_treatment\tdays_to_new_tumor_event_after_initial_treatment\tfollowup_treatment_success\tfollowup_sequence\tvital_status\tdays_to_last_followup\tdays_to_death\tperson_neoplasm_cancer_status\tnew_tumor_event_after_initial_treatment\tdays_to_new_tumor_event_after_initial_treatment\tfollowup_treatment_success\tfollowup_sequence\tvital_status\tdays_to_last_followup\tdays_to_death\tperson_neoplasm_cancer_status\tnew_tumor_event_after_initial_treatment\tdays_to_new_tumor_event_after_initial_treatment\tfollowup_treatment_success\n')
# for each file
# 1-make a new file name to write to
# 2-open the file to read from
# 3-create a header variable
# 4-create an info variable
# 5-parse out the root of the input file
# 6-call the processing function to process the list of elements (this is the recusion step)
# 7-open the file to write to and write the header and info to the outfile.
# 8-close the outfile and the infile

   for inputfile in filelist:
       
      # Parse the tree and get the patient barcode
      
       
      # Parse the names spaces and XML tree
      tree, ns = parse_and_get_ns(inputfile)        

      # Get root of tree
      root = tree.getroot()

      # Get the patient barcode
      barcode = root.getiterator(ns['shared']+"bcr_patient_barcode")[0].text
      info = barcode
      
      # make a new file name to write to
      new_out_file = outputdir + barcode + "_" + outputfile
      
      # create the header variable
      header = ""
      
      # create the content variable
      content = barcode
      
      # create the patient list to pass to the recursive routine
      patient = root[1].getchildren()
      
      # call the recursive function to parse the tree
      new_header, new_content = parse_xml_tree_recursive(patient, header, content, parse_tag(root[1].tag), 0)
      
      # write the new header and new content to a file
      out = open(new_out_file, "w")
      out.write(new_header)
      out.write("\n")
      out.write(new_content)
      out.write("\n")
      out.close()
#      
#      
#
#      # Get days_to_initial_pathologic_diagnosis
#      info = info + root.getiterator(ns['shared']+"days_to_initial_pathologic_diagnosis")[0].text + "\t"
#
#      # Get days_to_death
#      death=root.getiterator(ns['shared']+"days_to_death")
#      if death[0].text is None:
#         info = info + "NA" + "\t"
#      else:
#         info = info + death[0].text + "\t"
#
#      #	Get days_to_birth
#      birth = root.getiterator(ns['shared']+"days_to_birth")[0].text
#
#      if birth is None:
#         info = info + "NA" + "\t"
#      else:
#         info = info + birth + "\t"
#
#      #	Get days_to_last_known_alive
#      lastalive = root.getiterator(ns['shared']+"days_to_last_known_alive")[0].text
#
#      if lastalive is None:
#         info = info + "NA" + "\t"
#      else:
#       	 info = info + lastalive + "\t"
#
#      # For each follow up visit, get the information I need
#      try:
#         followups = root.getiterator(ns['follow_up_v1.0']+"follow_up")
#         for f in followups:
#            seq = f.attrib['sequence']
#            vital = f.find(ns['shared']+"vital_status").text if f.find(ns['shared']+"vital_status").attrib['procurement_status']=='Completed' else f.find(ns['shared']+"vital_status").attrib['procurement_status']
#            last_followup = f.find(ns['shared']+"days_to_last_followup").text if f.find(ns['shared']+"days_to_last_followup").attrib['procurement_status']=='Completed' else f.find(ns['shared']+"days_to_last_followup").attrib['procurement_status']
#            days_death = f.find(ns['shared']+"days_to_death").text if f.find(ns['shared']+"days_to_death").attrib['procurement_status']=='Completed' else f.find(ns['shared']+"days_to_death").attrib['procurement_status']
#            tumor_status = f.find(ns['shared']+"person_neoplasm_cancer_status").text if f.find(ns['shared']+"person_neoplasm_cancer_status").attrib['procurement_status']=='Completed' else f.find(ns['shared ']+"person_neoplasm_cancer_status").attrib['procurement_status']
#            nte = f.getiterator(ns['coad_nte']+"new_tumor_events")[0]
#            
#            new_event = nte.find(ns['nte']+"new_tumor_event_after_initial_treatment").text if nte.find(ns['nte']+"new_tumor_event_after_initial_treatment").attrib['procurement_status']=='Completed' else nte.find(ns['nte']+"new_tumor_event_after_initial_treatment").attrib['procurement_status']
#            days_to_nte = nte.find(ns['nte']+"days_to_new_tumor_event_after_initial_treatment").text if nte.find(ns['nte']+"days_to_new_tumor_event_after_initial_treatment") is not None else "Not in File"
#            
#            outcome = f.find(ns['shared']+"followup_treatment_success").text if f.find(ns['shared']+"followup_treatment_success").attrib['procurement_status']=='Completed' else f.find(ns['shared']+"followup_treatment_success").attrib['procurement_status']
#            alltext = [seq, vital, last_followup, days_death, tumor_status, new_event, days_to_nte,  outcome]
#            ["Not Avaliable" if v is None else v for v in alltext]
#            info = info + "\t".join(alltext) + "\t"
#            
#      except KeyError:
#         info = info + "No Followups Avaliable"
#
#      info = info + "\n"
#
#      out.write(info)

   # END for inputfile in filelist


   #close the output file
#out.close()

   print 'DONE!'


if __name__ == "__main__":
   main(sys.argv[1:])
#
#def parse_and_get_ns(file):
#   events = "start", "start-ns"
#   root = None
#   ns = {}
#   for event, elem in ET.iterparse(file, events):
#     if event == "start-ns":
#       if elem[0] in ns and ns[elem[0]] != elem[1]:
#         # NOTE: It is perfectly valid to have the same prefix refer
#         #     to different URI namespaces in different parts of the
#         #     document. This exception serves as a reminder that this
#         #     solution is not robust.    Use at your own peril.
#         raise KeyError("Duplicate prefix with different URI found.")
#       ns[elem[0]] = "{%s}" % elem[1]
#     elif event == "start":
#       if root is None:
#         root = elem
#   return ET.ElementTree(root), ns
