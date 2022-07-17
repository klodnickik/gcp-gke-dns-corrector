from flask import Flask, request, jsonify
import logging
import requests
import os
from google.cloud import dns
from google.cloud import compute


from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO)


dns_zone = os.environ.get('DNS_ZONE')
project_id = os.environ.get('PROJECT_ID')
zone = os.environ.get('COMPUTE_ZONE')
project_id = os.environ.get('PROJECT_ID')
compute_name = os.environ.get('COMPUTE_SERVER_NAME')
dns_prefix = os.environ.get('DNS_RECORD_PREFIX')

logging.info("Uruchamiam program poprawiajacy konfiguracje DNS")
logging.info("**** Environment variables:")
logging.info("** DNS_ZONE: {}".format(dns_zone))
logging.info("** PROJECT_ID: {}".format(project_id))
logging.info("** COMPUTE_ZONE: {}".format(zone))
logging.info("** COMPUTE_SERVER_NAME: {}".format(compute_name))
logging.info("** DNS_RECORD_PREFIX: {}".format(dns_prefix))


if (dns_zone==None):  logging.error("Missing env variable 'DNS_ZONE'")

app = Flask(__name__)


def OdczytajDNS(dns_zone_to_check, project_id):

	dns_znaleziony = False
	dns_rekordy_lista = []

	dns_client = dns.Client(project=project_id)

	dns_records_list = dns_client.list_zones()

	for zone in dns_records_list:
		if zone.dns_name == dns_zone: 
			dns_znaleziony=True
			dns_zone_rekord = zone.list_resource_record_sets()

	if dns_znaleziony == False:
		logging.error ("Nie znalazlem DNS {} w projekcie {}".format(dns_zone_to_check,project_id))
	else:
		logging.info ("Zona DNS {} znaleziona".format(dns_zone_to_check))

		# zona zostala znaleziona, sprawdzam rekordy


		for rekord in dns_zone_rekord:
			if rekord.record_type == 'A':
				pojedynczy_dns_rekord = {
					'dns_record_name': rekord.name,
					'dns_record_value': rekord.rrdatas,
				}

				dns_rekordy_lista.append(pojedynczy_dns_rekord)
				zone_id = rekord.zone
				zone_name = rekord.name

		logging.info("Rekordy ustawione przed zmianami:")
		logging.info(dns_rekordy_lista)

	return dns_znaleziony, dns_rekordy_lista, zone_id, zone_name



def SprawdzIPSerwerow(project_id, zone, compute_name):

	logging.info("Sprawdzam rzeczywiste adresy IP serwerow ...")
	servers_ip = []
	serwery = compute.InstancesClient()
	moje_serwery = serwery.list(project=project_id, zone=zone)

	for serwer in moje_serwery:
		if serwer.name.find(compute_name) >= 0:

			for nic in serwer.network_interfaces:
				logging.info("Znaleziono serwer {} z IP {}".format(serwer.name, nic.network_i_p))
				servers_ip.append(nic.network_i_p)

	return servers_ip


def zmien_ip_dla_domeny (compute_ip, required_dns_name, old_ip, zone_id):
	logging.info ("Zmieniam IP {} dla adresu {} (stara wartosc {})".format(compute_ip, required_dns_name, old_ip))

	compute_ip_list = []
	compute_ip_list.append(compute_ip)

	old_compute_ip_list = []
	old_compute_ip_list.append(old_ip)

	dns_changes = dns.Changes(zone=zone_id)

	OldDnsRecord = dns.ResourceRecordSet(name=required_dns_name, record_type='A', rrdatas=old_compute_ip_list, ttl=300, zone=zone_id)
	NewDnsRecord = dns.ResourceRecordSet(name=required_dns_name, record_type='A', rrdatas=compute_ip_list, ttl=300, zone=zone_id)

	dns_changes.delete_record_set(OldDnsRecord)
	dns_changes.add_record_set(NewDnsRecord)
	dns_changes.create()



def dodaj_dns (compute_ip, required_dns_name, zone_id):
	logging.info('Dodaje nowy rekord {} na {}'.format(required_dns_name, compute_ip))

	compute_ip_list = []
	compute_ip_list.append(compute_ip)

	dns_changes = dns.Changes(zone=zone_id)
	NewDnsRecord = dns.ResourceRecordSet(name=required_dns_name, record_type='A', rrdatas=compute_ip_list, ttl=300, zone=zone_id)
	dns_changes.add_record_set(NewDnsRecord)
	dns_changes.create()

def correct_allocation(compute_ip_list, dns_rekordy_lista, dns_prefix, zone_id):

	counter = 0
	diff_list = []

	for compute_ip in compute_ip_list:
		counter = counter + 1
		koniec_sprawdzania = False
		required_dns_name = dns_prefix + str(counter) + "." + dns_zone
		logging.info("Sprawdzam serwer nr {} z adresem IP {} i oczekiwanym rekordem DNS {}".format(counter, compute_ip, required_dns_name))

		# sprawdzam czy idealny rekord istnieje
		for dns_ip in dns_rekordy_lista:
			if (dns_ip["dns_record_value"][0] == compute_ip) and (dns_ip["dns_record_name"] == required_dns_name):
				logging.info("Rekord poprawny znaleziony.")
				koniec_sprawdzania = True
				diff_list.append("({}) {} correct".format(counter, compute_ip))

		for dns_ip in dns_rekordy_lista:
			if (dns_ip["dns_record_name"] == required_dns_name) and koniec_sprawdzania == False:
				logging.info("Znaleziony rekord DNS, wartosc adresu bledna, konieczna poprawa.")
				zmien_ip_dla_domeny(compute_ip, required_dns_name, dns_ip["dns_record_value"][0], zone_id)
				koniec_sprawdzania = True
				diff_list.append("({}) {} IP incorrect".format(counter, compute_ip))		

		if koniec_sprawdzania == False:
				logging.info("Nie znaleziono rekordu, konieczne jest jego dodanie")
				dodaj_dns(compute_ip, required_dns_name, zone_id)	
				diff_list.append("({}) {} IP missing".format(counter, compute_ip))	
	return diff_list





@app.route('/', methods=['GET'])
def request_main_page():
	zone_id = None

	zona_istnieje, dns_rekordy_lista, zone_id, zone_name = OdczytajDNS(dns_zone, zone_id)

	compute_ip_list = SprawdzIPSerwerow(project_id, zone, compute_name)

	diff_list = correct_allocation(compute_ip_list, dns_rekordy_lista, dns_prefix, zone_id)


	message = {
	'dns_zone' :  dns_zone,
	'dns_value_before_changes' : dns_rekordy_lista,
	'summary_of_validation' : diff_list
	}

	return jsonify(message)



if __name__ == "__main__":
	app.run(host='0.0.0.0', port=8080)