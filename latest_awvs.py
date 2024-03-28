#!/usr/bin/python
# -*- coding: UTF-8 -*-
import sys,os,time
import socket

from time import strftime,gmtime
version = sys.version_info
if version < (3, 0):
    print('The current version is not supported, you need to use python3')
    sys.exit()
import requests
import json,ast
from requests.packages.urllib3.exceptions import InsecureRequestWarning
import configparser
scan_label='script default label'
cf = configparser.ConfigParser()
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

print('Initializing~')
try:
    cf.read(r"config.ini",encoding='utf-8')
    secs=cf.sections()
    awvs_url =cf.get('awvs_url_key','awvs_url')
    apikey = cf.get('awvs_url_key','api_key')
    input_urls=cf.get('awvs_url_key','domain_file')
    excluded_paths = ast.literal_eval(cf.get('scan_seting', 'excluded_paths'))
    custom_headers = ast.literal_eval(cf.get('scan_seting', 'custom_headers'))
    limit_crawler_scope = cf.get('scan_seting', 'limit_crawler_scope').replace('\n', '').strip()  # 处理前后空格 与换行
    scan_speed = cf.get('scan_seting', 'scan_speed').replace('\n', '').strip()  # 处理前后空格 与换行
    scan_cookie = cf.get('scan_seting', 'cookie').replace('\n', '').strip()  # 处理前后空格 与换行
    proxy_enabled = cf.get('scan_seting', 'proxy_enabled').replace('\n', '').strip()  # 处理前后空格 与换行
    proxy_server = cf.get('scan_seting', 'proxy_server').replace('\n', '').strip()  # 处理前后空格 与换行
    webhook_url = cf.get('scan_seting', 'webhook_url').replace('\n', '').strip()  # 处理前后空格 与换行

except Exception as e:
    print('Initialization failed, failed to obtain config.ini, please check whether the configuration of the config.ini file is correct\n', e)
    sys.exit()

headers = {'Content-Type': 'application/json',"X-Auth": apikey}
add_count_suss=0
error_count=0
target_scan=False
target_list=[]



def push_wechat_group(content):
    global webhook_url
    try:
        # print('start pushing')
        # Change here to the webhook address of your own robot
        resp = requests.post(webhook_url,
                             json={"msgtype": "markdown",
                                   "markdown": {"content": content}})
        print(content)
        if 'invalid webhook url' in str(resp.text):
            print('The corporate WeChat key is invalid and cannot be pushed normally')
            sys.exit()
        if resp.json()["errcode"] != 0:
            raise ValueError("push wechat group failed, %s" % resp.text)
    except Exception as e:
        print(e)

#initial value
def message_push():#Check the number of high-risk vulnerabilities in a regular loop, and notify if there is a change
    try:
        get_target_url=awvs_url+'/api/v1/vulnerability_types?l=100&q=status:open;severity:3;'
        r = requests.get(get_target_url, headers=headers, timeout=30, verify=False)
        result = json.loads(r.content.decode())
        #print(result)
        init_high_count = 0
        for xxxx in result['vulnerability_types']:
            init_high_count=init_high_count+xxxx['count']
        print('current high risk:',init_high_count)
        while 1:
            try:
                time.sleep(30)
                r2 = requests.get(get_target_url, headers=headers, timeout=30, verify=False)
                result = json.loads(r2.content.decode())
                high_count = 0
                for xxxx in result['vulnerability_types']:
                    high_count = high_count + xxxx['count']
                #print(high_count,init_high_count)
                if high_count!=init_high_count:
                    current_date = str(strftime("%Y-%m-%d %H:%M:%S", gmtime()))
                    message_push=str(socket.gethostname())+'\n'+current_date+'\n'
                    for xxxx in result['vulnerability_types']:
                        message_push = message_push+'loophole: ' + xxxx['name'] + 'quantity: '+str(xxxx['count'])+'\n'
                    print(message_push)
                    push_wechat_group(message_push)
                    init_high_count=high_count
                else:
                    #print('No change in the number of high-risk vulnerabilities ',high_count)
                    init_high_count = high_count
            except Exception as e:
                print('Monitoring error, please check',e)
    except Exception as e:
        print(e)

def get_scan_status():# get scan status
    try:
        target_dict={}
        get_target_url=awvs_url+'/api/v1/me/stats'
        r = requests.get(get_target_url, headers=headers, timeout=30, verify=False)
        result = json.loads(r.content.decode())
        print('scanning:',result['scans_running_count'],'waiting to scan:',result['scans_waiting_count'],'scanned:',result['scans_conducted_count'],'Total number of vulnerabilities:',str(result['vuln_count'])+'\n major loopholes')
        for xxxx in result['top_vulnerabilities']:
            print('Vulnerability name:',xxxx['name'],' number of vulnerabilities:',xxxx['count'])
    except Exception as e:
        print(e)

def get_status():
    try:
        r = requests.get(awvs_url + '/api/v1/targets', headers=headers, timeout=10, verify=False)
        if r.status_code==401:
            print('awvs authentication failed, please check whether the api_key configured in config.ini is correct')
            sys.exit()
        if r.status_code==200 and 'targets' in str(r.text):
            pass
    except Exception as e:
        print('Initialization failed, please check whether the awvs_url in the config.ini file is correct\n',e)
        sys.exit()
    print('configured correctly~')
    get_scan_status()
get_status()

def get_target_list():#Get all targets in the scanner
    print('getting target')
    target_list=[]
    pages=0
    while 1:
        target_dict={}
        get_target_url=awvs_url+'/api/v1/targets?c={pages}&l=20'.format(pages=str(pages))
        r = requests.get(get_target_url, headers=headers, timeout=30, verify=False)
        result = json.loads(r.content.decode())
        try:
            for targetsid in range(len(result['targets'])):
                target_dict={'target_id':result['targets'][targetsid]['target_id'],'address':result['targets'][targetsid]['address']}
                target_list.append(target_dict)
            pages=pages+20

            if len(result['targets'])==0:
                return target_list
        except Exception as e:
            return r.text

def addTask(url,target):
    global scan_label
    try:
        url = ''.join((url, '/api/v1/targets/add'))
        data = {"targets":[{"address": target,"description":scan_label}],"groups":[]}
        r = requests.post(url, headers=headers, data=json.dumps(data), timeout=30, verify=False)
        result = json.loads(r.content.decode())
        return result['targets'][0]['target_id']
    except Exception as e:
        return e
def scan(url,target,profile_id,is_to_scan):
    global scan_label
    scanUrl = ''.join((url, '/api/v1/scans'))
    target_id = addTask(url,target)
    if target_id:
        try:
            configuration(url,target_id,target,profile_id)#Configure target parameters

            if is_to_scan:
                data = {"target_id": target_id, "profile_id": profile_id, "incremental": False,
                        "schedule": {"disable": False, "start_date": None, "time_sensitive": False}}
                response = requests.post(scanUrl, data=json.dumps(data), headers=headers, timeout=30, verify=False)
                result = json.loads(response.content)
                return [1,result['target_id']]
            else:
                print(target, 'The target is only added successfully')
                return [2,0]

        except Exception as e:
            print(e)

def configuration(url,target_id,target,default_scanning_profile_id):#configure target
    global custom_headers,excluded_paths,limit_crawler_scope,scan_cookie,scan_speed,proxy_enabled,proxy_server
    configuration_url = ''.join((url,'/api/v1/targets/{0}/configuration'.format(target_id)))
    if scan_cookie != '':#custom user's cookie
        data = {"scan_speed":scan_speed,"login":{"kind":"none"},"ssh_credentials":{"kind":"none"},"default_scanning_profile_id":default_scanning_profile_id,"sensor": False,"user_agent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko; compatible; GPTBot/1.0; +https://openai.com/gptbot) Chrome/117.0.0.0 Safari/537.36',"case_sensitive":"auto","limit_crawler_scope": limit_crawler_scope,"excluded_paths":excluded_paths,"authentication":{"enabled": False},"proxy":{"enabled": proxy_enabled,"protocol":"http","address":proxy_server.split(':')[0],"port":proxy_server.split(':')[1]},"technologies":[],"custom_headers":custom_headers,"custom_cookies":[{"url":target,"cookie":scan_cookie}],"debug":False,"client_certificate_password":"","issue_tracker_id":"","excluded_hours_id":""}
    else:

        data = {"scan_speed": scan_speed, "login": {"kind": "none"}, "ssh_credentials": {"kind": "none"},"default_scanning_profile_id":default_scanning_profile_id,
                "sensor": False, "user_agent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko; compatible; GPTBot/1.0; +https://openai.com/gptbot) Chrome/117.0.0.0 Safari/537.36', "case_sensitive": "auto",
                "limit_crawler_scope": limit_crawler_scope, "excluded_paths": excluded_paths,
                "authentication": {"enabled": False},
                "proxy": {"enabled": proxy_enabled, "protocol": "http", "address": proxy_server.split(':')[0], "port": proxy_server.split(':')[1]},
                "technologies": [], "custom_headers": custom_headers, "custom_cookies": [],
                "debug": False, "client_certificate_password": "", "issue_tracker_id": "", "excluded_hours_id": ""}

    r = requests.patch(url=configuration_url,data=json.dumps(data), headers=headers, timeout=30, verify=False)
    #print(configuration_url,r.text)

def delete_task():#Delete all scan tasks 
    global awvs_url, apikey, headers
    #print(123123)
    while 1:
        quer = '/api/v1/scans?l=20'
        try:
            r = requests.get(awvs_url+quer, headers=headers, timeout=30, verify=False)
            result = json.loads(r.content.decode())
            if int(len(result['scans'])) == 0:
                print('All scan tasks have been deleted, the current task is empty')
                return 0
            for targetsid in range(len(result['scans'])):
                task_id = result['scans'][targetsid]['scan_id']
                task_address = result['scans'][targetsid]['target']['address']
                try:
                    del_log=requests.delete(awvs_url+'/api/v1/scans/'+task_id,headers=headers, timeout=30, verify=False)
                    if del_log.status_code == 204:
                        print(task_address,' Delete scan task successfully')
                except Exception as e:
                    print(task_address,e)
        except Exception as e:
            print(awvs_url+quer,e)





def delete_targets():#Delete all scan targets and tasks
    global awvs_url,apikey,headers
    while 1:
        quer='/api/v1/targets'
        try:
            r = requests.get(awvs_url+quer, headers=headers, timeout=30, verify=False)
            result = json.loads(r.content.decode())
            if int(result['pagination']['count'])==0:
                print('All scan targets have been deleted, current target is empty')
                return 0
            for targetsid in range(len(result['targets'])):
                targets_id=result['targets'][targetsid]['target_id']
                targets_address = result['targets'][targetsid]['address']
                #print(targets_id,targets_address)
                try:
                    del_log=requests.delete(awvs_url+'/api/v1/targets/'+targets_id,headers=headers, timeout=30, verify=False)
                    if del_log.status_code == 204:
                        print(targets_address,' Target deleted successfully')
                except Exception as e:
                    print(targets_address,e)
        except Exception as e:
            print(awvs_url+quer,e)

def delete_finish():#Delete completed scans
    global awvs_url,apikey,headers
    while 1:
        quer='/api/v1/scans?l=10&q=status:completed;&s=status:asc'
        try:
            r = requests.get(awvs_url+quer, headers=headers, timeout=30, verify=False)
            result = json.loads(r.content.decode())
            if int(result['pagination']['count']) == 0:
                print('Scan completed target has been deleted, current scanned completed target is empty')
                return 0
            for target_id in result['scans']:
                #print(target_id['target_id'])
                try:
                    del_log=requests.delete(awvs_url+'/api/v1/scans/'+target_id['scan_id'],headers=headers, timeout=30, verify=False)
                    if del_log.status_code == 204:
                        print(target_id['target']['address'],' Completed the goal, deleted the scan successfully')
                except Exception as e:
                    print(target_id['target']['address'],e)
        except Exception as e:
            print('Report an error, delete the scan that has been scanned',e)

def custom_log4j():  # Add custom scan log4j
    get_target_url = awvs_url + '/api/v1/scanning_profiles'
    # log4j
    post_data = {"name":"Apache Log4j RCE","custom":'true',"checks":["wvs/Scripts/PerFile","wvs/Scripts/PerFolder","wvs/Scripts/PerScheme/ASP_Code_Injection.script","wvs/Scripts/PerScheme/PHP_Deserialization_Gadgets.script","wvs/Scripts/PerScheme/Arbitrary_File_Creation.script","wvs/Scripts/PerScheme/Arbitrary_File_Deletion.script","wvs/Scripts/PerScheme/Blind_XSS.script","wvs/Scripts/PerScheme/CRLF_Injection.script","wvs/Scripts/PerScheme/Code_Execution.script","wvs/Scripts/PerScheme/Directory_Traversal.script","wvs/Scripts/PerScheme/Email_Header_Injection.script","wvs/Scripts/PerScheme/Email_Injection.script","wvs/Scripts/PerScheme/Error_Message.script","wvs/Scripts/PerScheme/Expression_Language_Injection.script","wvs/Scripts/PerScheme/File_Inclusion.script","wvs/Scripts/PerScheme/File_Tampering.script","wvs/Scripts/PerScheme/File_Upload.script","wvs/Scripts/PerScheme/Generic_Oracle_Padding.script","wvs/Scripts/PerScheme/HTTP_Parameter_Pollution.script","wvs/Scripts/PerScheme/Host_Based_Attack_Reset_Password.script","wvs/Scripts/PerScheme/LDAP_Injection.script","wvs/Scripts/PerScheme/Long_Password_Denial_of_Service.script","wvs/Scripts/PerScheme/MongoDB_Injection.script","wvs/Scripts/PerScheme/NodeJs_Injection.script","wvs/Scripts/PerScheme/PHP_Code_Injection.script","wvs/Scripts/PerScheme/RubyOnRails_Code_Injection.script","wvs/Scripts/PerScheme/Perl_Code_Injection.script","wvs/Scripts/PerScheme/PHP_User_Controlled_Vulns.script","wvs/Scripts/PerScheme/Rails_Mass_Assignment.script","wvs/Scripts/PerScheme/Rails_Where_SQL_Injection.script","wvs/Scripts/PerScheme/Rails_render_inline_RCE.script","wvs/Scripts/PerScheme/Remote_File_Inclusion_XSS.script","wvs/Scripts/PerScheme/Script_Source_Code_Disclosure.script","wvs/Scripts/PerScheme/Server_Side_Request_Forgery.script","wvs/Scripts/PerScheme/Sql_Injection.script","wvs/Scripts/PerScheme/Struts_RCE_S2-053_CVE-2017-12611.script","wvs/Scripts/PerScheme/Struts_RCE_S2_029.script","wvs/Scripts/PerScheme/Unsafe_preg_replace.script","wvs/Scripts/PerScheme/XFS_and_Redir.script","wvs/Scripts/PerScheme/XML_External_Entity_Injection.script","wvs/Scripts/PerScheme/XPath_Injection.script","wvs/Scripts/PerScheme/XSS.script","wvs/Scripts/PerScheme/ESI_Injection.script","wvs/Scripts/PerScheme/Java_Deserialization.script","wvs/Scripts/PerScheme/Pickle_Serialization.script","wvs/Scripts/PerScheme/Python_Code_Injection.script","wvs/Scripts/PerScheme/Argument_Injection.script","wvs/Scripts/PerScheme/DotNet_BinaryFormatter_Deserialization.script","wvs/Scripts/PerScheme/Apache_Solr_Parameter_Injection.script","wvs/Scripts/PerScheme/Cmd_Hijack_Windows.script","wvs/Scripts/PerScheme/JWT_Param_Audit.script","wvs/Scripts/PerServer","wvs/Scripts/PostCrawl","wvs/Scripts/PostScan","wvs/Scripts/WebApps","wvs/RPA","wvs/Crawler","wvs/httpdata","wvs/target/rails_sprockets_path_traversal.js","wvs/target/web_cache_poisoning.js","wvs/target/aux_systems_ssrf.js","wvs/target/proxy_misrouting_ssrf.js","wvs/target/http_01_ACME_challenge_xss.js","wvs/target/java_melody_detection_plus_xxe.js","wvs/target/uwsgi_path_traversal.js","wvs/target/weblogic_rce_CVE-2018-3245.js","wvs/target/php_xdebug_rce.js","wvs/target/nginx_integer_overflow_CVE-2017-7529.js","wvs/target/jupyter_notebook_rce.js","wvs/target/hadoop_yarn_resourcemanager.js","wvs/target/couchdb_rest_api.js","wvs/target/activemq_default_credentials.js","wvs/target/apache_mod_jk_access_control_bypass.js","wvs/target/mini_httpd_file_read_CVE-2018-18778.js","wvs/target/osgi_management_console_default_creds.js","wvs/target/docker_engine_API_exposed.js","wvs/target/docker_registry_API_exposed.js","wvs/target/jenkins_audit.js","wvs/target/thinkphp_5_0_22_rce.js","wvs/target/uwsgi_unauth.js","wvs/target/fastcgi_unauth.js","wvs/target/apache_balancer_manager.js","wvs/target/cisco_ise_stored_xss.js","wvs/target/horde_imp_rce.js","wvs/target/nagiosxi_556_rce.js","wvs/target/next_js_arbitrary_file_read.js","wvs/target/php_opcache_status.js","wvs/target/opencms_solr_xxe.js","wvs/target/redis_open.js","wvs/target/memcached_open.js","wvs/target/Weblogic_async_rce_CVE-2019-2725.js","wvs/target/Weblogic_T3_XXE_CVE-2019-2647.js","wvs/target/RevProxy_Detection.js","wvs/target/cassandra_open.js","wvs/target/nagiosxi_sqli_CVE-2018-8734.js","wvs/target/backdoor_bootstrap_sass.js","wvs/target/apache_spark_audit.js","wvs/target/fortigate_file_reading.js","wvs/target/pulse_sslvpn_file_reading.js","wvs/target/SAP_Hybris_virtualjdbc_RCE_CVE-2019-0344.js","wvs/target/webmin_rce_1_920_CVE-2019-15107.js","wvs/target/Weblogic_T3_XXE_CVE-2019-2888.js","wvs/target/citrix_netscaler_CVE-2019-19781.js","wvs/target/DotNet_HTTP_Remoting.js","wvs/target/opensearch-target.js","wvs/target/adminer-4.6.2-file-disclosure-vulnerability.js","wvs/target/apache_mod_rewrite_open_redirect_CVE-2019-10098.js","wvs/target/default_apple-app-site-association.js","wvs/target/golang-debug-pprof.js","wvs/target/openid_connect_discovery.js","wvs/target/nginx-plus-unprotected-status.js","wvs/target/nginx-plus-unprotected-api.js","wvs/target/nginx-plus-unprotected-dashboard.js","wvs/target/nginx-plus-unprotected-upstream.js","wvs/target/Kentico_CMS_Audit.js","wvs/target/Rails_DoubleTap_RCE_CVE-2019-5418.js","wvs/target/Oracle_EBS_Audit.js","wvs/target/rce_sql_server_reporting_services.js","wvs/target/liferay_portal_jsonws_rce.js","wvs/target/php_opcache_gui.js","wvs/target/check_acumonitor.js","wvs/target/spring_cloud_config_server_CVE-2020-5410.js","wvs/target/f5_big_ip_tmui_rce_CVE-2020-5902.js","wvs/target/rack_mini_profiler_information_disclosure.js","wvs/target/grafana_ssrf_rce_CVE-2020-13379.js","wvs/target/h2-console.js","wvs/target/jolokia_xxe.js","wvs/target/rails_rce_locals_CVE-2020-8163.js","wvs/target/Cisco_ASA_Path_Traversal_CVE-2020-3452.js","wvs/target/DNN_Deser_Cookie_CVE-2017-9822.js","wvs/target/404_text_search.js","wvs/target/totaljs_dir_traversal_CVE-2019-8903.js","wvs/target/OFBiz_xmlrpc_deser_rce_CVE-2020-9496.js","wvs/target/http_redirections.js","wvs/target/apache_zookeeper_open.js","wvs/target/apache_kafka_open.js","wvs/target/nette_framework_rce_CVE-2020-15227.js","wvs/target/vmware_vcenter_unauth_file_read.js","wvs/target/mobile_iron_rce_CVE-2020-15505.js","wvs/target/web_cache_poisoning_dos.js","wvs/target/prototype_pollution_target.js","wvs/target/openfire_admin_console_ssrf_CVE-2019-18394.js","wvs/target/weblogic_rce_CVE-2020-14882.js","wvs/target/Weblogic_IIOP_RCE_CVE-2020-2551.js","wvs/target/Odoo_audit.js","wvs/target/citrix_xenmobile_arbitrary_file_read_CVE-2020-8209.js","wvs/target/sonarqube_default_credentials.js","wvs/target/common_api_endpoints.js","wvs/target/Unomi_MVEL_RCE_CVE-2020-13942.js","wvs/target/symfony_weak_secret_rce.js","wvs/target/lucee_arbitrary_file_write.js","wvs/target/dynamic_rendering_engines.js","wvs/target/open_prometheus.js","wvs/target/open_monitoring.js","wvs/target/apache_flink_path_traversal_CVE-2020-17519.js","wvs/target/imageresizer_debug.js","wvs/target/unprotected_apache_nifi.js","wvs/target/unprotected_kong_gateway_adminapi_interface.js","wvs/target/sap_solution_manager_rce_CVE-2020-6207.js","wvs/target/sonicwall_ssl_vpn_rce_jarrewrite.js","wvs/target/nodejs_debugger_open.js","wvs/target/vmware_vcenter_server_unauth_rce_CVE-2021-21972.js","wvs/target/paloalto-pan-os-xss-CVE-2020-2036.js","wvs/target/golang_delve_debugger_open.js","wvs/target/microsoft_exchange-server-ssrf-CVE-2021-26855.js","wvs/target/python_debugpy_debugger_open.js","wvs/target/AppWeb_auth_bypass_CVE-2018-8715.js","wvs/target/OFBiz_SOAPService_deser_rce_CVE-2021-26295.js","wvs/target/vhost_files_locs_misconfig.js","wvs/target/cockpit_nosqli_CVE-2020-35847.js","wvs/target/f5_iControl_REST_RCE_CVE-2021-22986.js","wvs/target/Cisco_RV_auth_bypass_CVE-2021-1472.js","wvs/target/web_installer_exposed.js","wvs/target/ntopng_auth_bypass_CVE-2021-28073.js","wvs/target/request_smuggling.js","wvs/target/Hashicorp_Consul_exposed.js","wvs/target/django_debug_toolbar.js","wvs/target/VMware_vRealize_SSRF_CVE-2021-21975.js","wvs/target/GravCMS_unauth_RCE_CVE-2021-21425.js","wvs/target/caddy_unprotected_api.js","wvs/target/dragonfly_arbitrary_file_read_CVE-2021-33564.js","wvs/target/bitrix_audit.js","wvs/target/open_redirect.js","wvs/target/gitlab_audit.js","wvs/target/nacos_auth_bypass_CVE-2021-29441.js","wvs/target/sap_bo_bip_ssrf_CVE-2020-6308.js","wvs/target/detect_apache_shiro_server.js","wvs/target/jetty_concat_inf_disc_CVE-2021-28164.js","wvs/target/RethinkDB_open.js","wvs/target/spring_boot_actuator_logview_path_trav_CVE-2021-21234.js","wvs/target/open_webpagetest.js","wvs/target/buddypress_rest_api_privesc_CVE-2021-21389.js","wvs/target/Hasura_GraphQL_SSRF.js","wvs/target/grandnode_path_traversal_CVE-2019-12276.js","wvs/target/SearchBlox_File_Inclusion_CVE-2020-35580.js","wvs/target/Zimbra_SSRF_CVE-2020-7796.js","wvs/target/jetty_inf_disc_CVE-2021-34429.js","wvs/target/Cisco_ASA_XSS_CVE-2020-3580.js","wvs/target/haproxy_unprotected_api.js","wvs/target/kong_unprotected_api.js","wvs/target/OData_feed_accessible_anonymously.js","wvs/target/Confluence_OGNL_Injection_CVE-2021-26084.js","wvs/target/microsoft_exchange_preauth_path_confusion_CVE-2021-34473.js","wvs/target/Atlassian_Jira_File_Read_CVE-2021-26086.js","wvs/target/ManageEngine_ADSelfService_Plus_auth_bypass_CVE-2021-40539.js","wvs/target/Django_Debug_Mode.js","wvs/target/Payara_Micro_File_Read_CVE-2021-41381.js","wvs/target/keycloak_request_uri_SSRF_CVE-2020-10770.js","wvs/target/apache_mod_proxy_SSRF_CVE-2021-40438.js","wvs/target/apache_insecure_path_norm_CVE-2021-41773_CVE-2021-42013.js","wvs/target/gitlab_exiftool_rce_CVE-2021-22205.js","wvs/target/http2/http2_pseudo_header_ssrf.js","wvs/target/Sitecore_XP_RCE_CVE-2021-42237.js","wvs/target/http2/http2_misrouting_ssrf.js","wvs/target/http2/http2_web_cache_poisoning.js","wvs/target/http2/http2_web_cache_poisoning_dos.js","wvs/input_group","wvs/deepscan","wvs/custom-scripts","wvs/MalwareScanner","wvs/location/zabbix/zabbix_audit.js","wvs/location/reverse_proxy_path_traversal.js","wvs/location/cors_origin_validation.js","wvs/location/yii2/yii2_gii.js","wvs/location/nodejs_source_code_disclosure.js","wvs/location/npm_debug_log.js","wvs/location/php_cs_cache.js","wvs/location/laravel_log_viewer_lfd.js","wvs/location/sap_b2b_lfi.js","wvs/location/nodejs_path_traversal_CVE-2017-14849.js","wvs/location/jquery_file_upload_rce.js","wvs/location/goahead_web_server_rce.js","wvs/location/file_upload_via_put_method.js","wvs/location/coldfusion/coldfusion_rds_login.js","wvs/location/coldfusion/coldfusion_request_debugging.js","wvs/location/coldfusion/coldfusion_robust_exception.js","wvs/location/coldfusion/coldfusion_add_paths.js","wvs/location/coldfusion/coldfusion_amf_deser.js","wvs/location/coldfusion/coldfusion_jndi_inj_rce.js","wvs/location/coldfusion/coldfusion_file_uploading_CVE-2018-15961.js","wvs/location/python_source_code_disclosure.js","wvs/location/ruby_source_code_disclosure.js","wvs/location/confluence/confluence_widget_SSTI_CVE-2019-3396.js","wvs/location/shiro/apache-shiro-deserialization-rce.js","wvs/location/coldfusion/coldfusion_flashgateway_deser_CVE-2019-7091.js","wvs/location/oraclebi/oracle_biee_convert_xxe_CVE-2019-2767.js","wvs/location/oraclebi/oracle_biee_adfresource_dirtraversal_CVE-2019-2588.js","wvs/location/oraclebi/oracle_biee_authbypass_CVE-2019-2768.js","wvs/location/oraclebi/oracle_biee_ReportTemplateService_xxe_CVE-2019-2616.js","wvs/location/oraclebi/oracle_biee_default_creds.js","wvs/location/hidden_parameters.js","wvs/location/asp_net_resolveurl_xss.js","wvs/location/oraclebi/oracle_biee_amf_deser_rce_CVE-2020-2950.js","wvs/location/composer_installed_json.js","wvs/location/typo3/typo3_audit.js","wvs/location/config_json_files_secrets_leakage.js","wvs/location/import_swager_files_from_common_locations.js","wvs/location/forgerock/forgerock_openam_deser_rce_CVE-2021-35464.js","wvs/location/web_cache_poisoning_dos_for_js.js","wvs/location/forgerock/forgerock_openam_ldap_inj_CVE-2021-29156.js","wvs/location/ghost/Ghost_Theme_Preview_XSS_CVE-2021-29484.js","wvs/location/qdpm/qdPM_Inf_Disclosure.js","wvs/location/apache_source_code_disclosure.js","wvs/location/oraclebi/oracle_biee_ReportTemplateService_xxe_CVE-2021-2400.js","ovas/"]}

    r = requests.post(get_target_url, data=json.dumps(post_data), headers=headers, timeout=30, verify=False)
    result = json.loads(r.content.decode())
    get_target_url = awvs_url + '/api/v1/scanning_profiles'
    r = requests.get(get_target_url, headers=headers, timeout=30, verify=False)
    result = json.loads(r.content.decode())
    for xxx in result['scanning_profiles']:
        if xxx['name']=='Apache Log4j RCE':
            return xxx['profile_id']

def custom_bug_bounty():  # Add custom scan bug_bounty
    get_target_url = awvs_url + '/api/v1/scanning_profiles'
    # log4j
    post_data = {"name":"Bug Bounty","custom":'true',"checks":["wvs/Scripts/PerFile/Backup_File.script","wvs/Scripts/PerFile/Bash_RCE.script","wvs/Scripts/PerFile/HTML_Form_In_Redirect_Page.script","wvs/Scripts/PerFile/Hashbang_Ajax_Crawling.script","wvs/Scripts/PerFile/Javascript_AST_Parse.script","wvs/Scripts/PerFile/Javascript_Libraries_Audit.script","wvs/Scripts/PerFile/PHP_SuperGlobals_Overwrite.script","wvs/Scripts/PerFile/REST_Discovery_And_Audit_File.script","wvs/Scripts/PerFile/Apache_Tomcat_Information_Disclosure_CVE-2017-12616.script","wvs/Scripts/PerFolder/APC.script","wvs/Scripts/PerFolder/ASP-NET_Application_Trace.script","wvs/Scripts/PerFolder/ASP-NET_Debugging_Enabled.script","wvs/Scripts/PerFolder/ASP-NET_Diagnostic_Page.script","wvs/Scripts/PerFolder/Basic_Auth_Over_HTTP.script","wvs/Scripts/PerFolder/Bazaar_Repository.script","wvs/Scripts/PerFolder/CVS_Repository.script","wvs/Scripts/PerFolder/Core_Dump_Files.script","wvs/Scripts/PerFolder/Dreamweaver_Scripts.script","wvs/Scripts/PerFolder/HTML_Form_In_Redirect_Page_Dir.script","wvs/Scripts/PerFolder/Http_Verb_Tampering.script","wvs/Scripts/PerFolder/IIS51_Directory_Auth_Bypass.script","wvs/Scripts/PerFolder/JetBrains_Idea_Project_Directory.script","wvs/Scripts/PerFolder/REST_Discovery_And_Audit_Folder.script","wvs/Scripts/PerFolder/Readme_Files.script","wvs/Scripts/PerFolder/SVN_Repository.script","wvs/Scripts/PerFolder/Trojan_Scripts.script","wvs/Scripts/PerFolder/WS_FTP_log_file.script","wvs/Scripts/PerFolder/htaccess_File_Readable.script","wvs/Scripts/PerFolder/Deadjoe_file.script","wvs/Scripts/PerFolder/Spring_Boot_WhiteLabel_Error_Page_SPEL.script","wvs/Scripts/PerFolder/Spring_Security_Auth_Bypass_CVE-2016-5007.script","wvs/Scripts/PerScheme/Error_Message.script","wvs/Scripts/PerScheme/File_Upload.script","wvs/Scripts/PerScheme/Generic_Oracle_Padding.script","wvs/Scripts/PerScheme/Long_Password_Denial_of_Service.script","wvs/Scripts/PerScheme/PHP_User_Controlled_Vulns.script","wvs/Scripts/PerScheme/Rails_Mass_Assignment.script","wvs/Scripts/PerScheme/Unsafe_preg_replace.script","wvs/Scripts/PerScheme/XFS_and_Redir.script","wvs/Scripts/PerScheme/XPath_Injection.script","wvs/Scripts/PerScheme/ESI_Injection.script","wvs/Scripts/PerScheme/DotNet_BinaryFormatter_Deserialization.script","wvs/Scripts/PerServer/AJP_Audit.script","wvs/Scripts/PerServer/ASP_NET_Error_Message.script","wvs/Scripts/PerServer/ASP_NET_Forms_Authentication_Bypass.script","wvs/Scripts/PerServer/Apache_Axis2_Audit.script","wvs/Scripts/PerServer/Apache_Geronimo_Default_Administrative_Credentials.script","wvs/Scripts/PerServer/Apache_Proxy_CONNECT_Enabled.script","wvs/Scripts/PerServer/Apache_Roller_Audit.script","wvs/Scripts/PerServer/Apache_Running_As_Proxy.script","wvs/Scripts/PerServer/Apache_Server_Information.script","wvs/Scripts/PerServer/Apache_Solr_Exposed.script","wvs/Scripts/PerServer/Apache_Unfiltered_Expect_Header_Injection.script","wvs/Scripts/PerServer/Apache_httpOnly_Cookie_Disclosure.script","wvs/Scripts/PerServer/Apache_mod_negotiation_Filename_Bruteforcing.script","wvs/Scripts/PerServer/ColdFusion_Audit.script","wvs/Scripts/PerServer/ColdFusion_User_Agent_XSS.script","wvs/Scripts/PerServer/Frontpage_Extensions_Enabled.script","wvs/Scripts/PerServer/Frontpage_Information.script","wvs/Scripts/PerServer/Frontpage_authors_pwd.script","wvs/Scripts/PerServer/GlassFish_Audit.script","wvs/Scripts/PerServer/Hadoop_Cluster_Web_Interface.script","wvs/Scripts/PerServer/Horde_IMP_Webmail_Exploit.script","wvs/Scripts/PerServer/Ioncube_Loader_Wizard.script","wvs/Scripts/PerServer/JBoss_Audit.script","wvs/Scripts/PerServer/JBoss_Status_Servlet_Information_Leak.script","wvs/Scripts/PerServer/JBoss_Web_Service_Console.script","wvs/Scripts/PerServer/Java_Debug_Wire_Protocol_Audit.script","wvs/Scripts/PerServer/Jetty_Audit.script","wvs/Scripts/PerServer/Lotus_Domino_crlf_xss.script","wvs/Scripts/PerServer/Misfortune_Cookie.script","wvs/Scripts/PerServer/MongoDB_Audit.script","wvs/Scripts/PerServer/Movable_Type_4_RCE.script","wvs/Scripts/PerServer/Oracle_Application_Logs.script","wvs/Scripts/PerServer/Oracle_Reports_Audit.script","wvs/Scripts/PerServer/PHP_CGI_RCE_Force_Redirect.script","wvs/Scripts/PerServer/PHP_Hash_Collision_Denial_Of_Service.script","wvs/Scripts/PerServer/Parallels_Plesk_Audit.script","wvs/Scripts/PerServer/Pyramid_Debug_Mode.script","wvs/Scripts/PerServer/Railo_Audit.script","wvs/Scripts/PerServer/Registration_Page.script","wvs/Scripts/PerServer/SSL_Audit.script","wvs/Scripts/PerServer/Same_Site_Scripting.script","wvs/Scripts/PerServer/Snoop_Servlet.script","wvs/Scripts/PerServer/Spring_Boot_Actuator.script","wvs/Scripts/PerServer/Tomcat_Audit.script","wvs/Scripts/PerServer/Tomcat_Status_Page.script","wvs/Scripts/PerServer/Track_Trace_Server_Methods.script","wvs/Scripts/PerServer/VirtualHost_Audit.script","wvs/Scripts/PerServer/WAF_Detection.script","wvs/Scripts/PerServer/Web_Server_Default_Welcome_Page.script","wvs/Scripts/PerServer/Web_Statistics.script","wvs/Scripts/PerServer/Zend_Framework_Config_File.script","wvs/Scripts/PerServer/elasticsearch_Audit.script","wvs/Scripts/PerServer/elmah_Information_Disclosure.script","wvs/Scripts/PostCrawl/Adobe_Flex_Audit.script","wvs/Scripts/PostCrawl/Apache_CN_Discover_New_Files.script","wvs/Scripts/PostCrawl/Azure_Blobs_Audit.script","wvs/Scripts/PostCrawl/CKEditor_Audit.script","wvs/Scripts/PostCrawl/CakePHP_Audit.script","wvs/Scripts/PostCrawl/Config_File_Disclosure.script","wvs/Scripts/PostCrawl/FCKEditor_Audit.script","wvs/Scripts/PostCrawl/GWT_Audit.script","wvs/Scripts/PostCrawl/Genericons_Audit.script","wvs/Scripts/PostCrawl/IIS_Tilde_Dir_Enumeration.script","wvs/Scripts/PostCrawl/J2EE_Audit.script","wvs/Scripts/PostCrawl/JAAS_Authentication_Bypass.script","wvs/Scripts/PostCrawl/JBoss_Seam_Remoting.script","wvs/Scripts/PostCrawl/JBoss_Seam_actionOutcome.script","wvs/Scripts/PostCrawl/JSP_Authentication_Bypass.script","wvs/Scripts/PostCrawl/MS15-034.script","wvs/Scripts/PostCrawl/Minify_Audit.script","wvs/Scripts/PostCrawl/OFC_Upload_Image_Audit.script","wvs/Scripts/PostCrawl/PrimeFaces5_EL_Injection.script","wvs/Scripts/PostCrawl/Rails_Audit.script","wvs/Scripts/PostCrawl/Rails_Audit_Routes.script","wvs/Scripts/PostCrawl/Server_Source_Code_Disclosure.script","wvs/Scripts/PostCrawl/Session_Fixation.script","wvs/Scripts/PostCrawl/SharePoint_Audit.script","wvs/Scripts/PostCrawl/Timthumb_Audit.script","wvs/Scripts/PostCrawl/Tiny_MCE_Audit.script","wvs/Scripts/PostCrawl/Uploadify_Audit.script","wvs/Scripts/PostCrawl/WADL_Files.script","wvs/Scripts/PostCrawl/WebDAV_Audit.script","wvs/Scripts/PostCrawl/XML_Quadratic_Blowup_Attack.script","wvs/Scripts/PostCrawl/Zend_Framework_LFI_via_XXE.script","wvs/Scripts/PostCrawl/phpLiteAdmin_Audit.script","wvs/Scripts/PostCrawl/phpThumb_Audit.script","wvs/Scripts/PostCrawl/tcpdf_Audit.script","wvs/Scripts/PostCrawl/X_Forwarded_For.script","wvs/Scripts/PostCrawl/Host_Header_Attack.script","wvs/target/ssltest","wvs/Scripts/PerFolder/Development_Files.script","wvs/deepscan/dom_xss","wvs/deepscan/javascript_library_audit_deepscan.js","wvs/MalwareScanner","wvs/target/default_apple-app-site-association.js","wvs/target/apache_mod_rewrite_open_redirect_CVE-2019-10098.js","wvs/target/openid_connect_discovery.js","wvs/target/f5_big_ip_tmui_rce_CVE-2020-5902.js","wvs/Scripts/WebApps/CMSMS.script","wvs/Scripts/WebApps/codeigniter.script","wvs/Scripts/WebApps/confluence.script","wvs/Scripts/WebApps/dotnetnuke.script","wvs/Scripts/WebApps/drupal.script","wvs/Scripts/WebApps/drupal_2.script","wvs/Scripts/WebApps/ektroncms.script","wvs/Scripts/WebApps/gallery.script","wvs/Scripts/WebApps/horde.script","wvs/Scripts/WebApps/ipb.script","wvs/Scripts/WebApps/jira.script","wvs/Scripts/WebApps/joomla.script","wvs/Scripts/WebApps/joomla_12.script","wvs/Scripts/WebApps/joomla_13.script","wvs/Scripts/WebApps/joomla_3.script","wvs/Scripts/WebApps/joomla_4.script","wvs/Scripts/WebApps/joomla_5.script","wvs/Scripts/WebApps/joomla_7.script","wvs/Scripts/WebApps/joomla_8.script","wvs/Scripts/WebApps/joomla_9.script","wvs/Scripts/WebApps/kayakofusion.script","wvs/Scripts/WebApps/liferay.script","wvs/Scripts/WebApps/magento.script","wvs/Scripts/WebApps/mantisbt.script","wvs/Scripts/WebApps/mediawiki.script","wvs/Scripts/WebApps/moinmoin.script","wvs/Scripts/WebApps/movabletype.script","wvs/Scripts/WebApps/nagios.script","wvs/Scripts/WebApps/openx.script","wvs/Scripts/WebApps/phpmyadmin.script","wvs/Scripts/WebApps/pmwiki.script","wvs/Scripts/WebApps/roundcube.script","wvs/Scripts/WebApps/sharepoint.script","wvs/Scripts/WebApps/symfony.script","wvs/Scripts/WebApps/symphony.script","wvs/Scripts/WebApps/TikiWiki.script","wvs/Scripts/WebApps/typo3.script","wvs/Scripts/WebApps/umbraco.script","wvs/Scripts/WebApps/vbulletin.script","wvs/Scripts/WebApps/wordpress.script","wvs/Scripts/WebApps/wordpress_1.script","wvs/Scripts/WebApps/wordpress_10.script","wvs/Scripts/WebApps/wordpress_11.script","wvs/Scripts/WebApps/wordpress_12.script","wvs/Scripts/WebApps/wordpress_13.script","wvs/Scripts/WebApps/wordpress_14.script","wvs/Scripts/WebApps/wordpress_15.script","wvs/Scripts/WebApps/wordpress_16.script","wvs/Scripts/WebApps/wordpress_19.script","wvs/Scripts/WebApps/wordpress_3.script","wvs/Scripts/WebApps/wordpress_4.script","wvs/Scripts/WebApps/wordpress_5.script","wvs/Scripts/WebApps/wordpress_6.script","wvs/Scripts/WebApps/wordpress_7.script","wvs/Scripts/WebApps/wordpress_9.script","wvs/Scripts/WebApps/xcart.script","wvs/Scripts/WebApps/drupal_5.script","wvs/Scripts/WebApps/jira_1.script","wvs/Scripts/WebApps/wordpress_21.script","wvs/Scripts/WebApps/jira_3.script","wvs/Scripts/WebApps/liferay_2.script","wvs/Scripts/WebApps/drupal_6.script","wvs/Scripts/WebApps/wordpress_23.script","wvs/Scripts/WebApps/ektroncms_1.script","wvs/Scripts/WebApps/wordpress_24.script","wvs/Scripts/WebApps/SAPNetWeaver_1.script","wvs/Scripts/WebApps/SAPNetWeaver_3.script","wvs/Scripts/WebApps/SAPNetWeaver_4.script","wvs/Scripts/WebApps/SAPNetWeaver_10.script","wvs/Scripts/WebApps/SAPNetWeaver_12.script","wvs/Scripts/WebApps/wordpress_25.script","wvs/Scripts/WebApps/wordpress_26.script","wvs/Scripts/WebApps/SAPNetWeaver_15.script","wvs/Scripts/WebApps/jira_5.script","wvs/Scripts/WebApps/jira_6.script","wvs/Scripts/WebApps/jira_7.script","wvs/target/Kentico_CMS_Audit.js","wvs/target/next_js_audit.js","wvs/httpdata/12-Malware.js","wvs/httpdata/request_url_override.js","wvs/httpdata/cors_acao.js","wvs/httpdata/HSTS_not_implemented.js","wvs/httpdata/X_Frame_Options_not_implemented.js","wvs/httpdata/javascript_library_audit_external.js","wvs/httpdata/web_cache_deception.js","wvs/httpdata/graphql_audit.js","wvs/location/nodejs_source_code_disclosure.js","wvs/location/web_cache_poisoning_dos_for_js.js","wvs/Crawler","wvs/RPA/InsecureTransition.js","wvs/RPA/Content_Type_Missing.js","wvs/RPA/Session_Token_In_Url.js","wvs/RPA/Password_In_Get.js","wvs/RPA/Cookie_On_Parent_Domain.js","wvs/RPA/Cookie_Without_HttpOnly.js","wvs/RPA/Cookie_Without_Secure.js","wvs/RPA/Cacheable_Sensitive_Page.js","wvs/RPA/Unencrypted_VIEWSTATE.js","wvs/RPA/SRI_Not_Implemented.js","wvs/RPA/no_https.js","wvs/RPA/Express_Cookie_Session_Weak_Secret.js","wvs/RPA/Express_Express_Session_Weak_Secret.js","wvs/RPA/Universal_Cookie_Weak_Secret.js","wvs/RPA/JWT_Cookie_Audit.js","wvs/RPA/Play_Cookie_Weak_Secret.js","wvs/RPA/Cookie_Validator.js","wvs/RPA/Pyramid_Cookie_Weak_Secret.js","wvs/RPA/F5_BIGIP_Cookie_Info_Disclosure.js","wvs/Scripts/PerServer/Version_Check.script","wvs/Scripts/PostCrawl/Amazon_S3_Buckets_Audit.script","wvs/Scripts/PostScan/9-Multiple_Web_Servers.script","ovas/"]}

    r = requests.post(get_target_url, data=json.dumps(post_data), headers=headers, timeout=30, verify=False)
    result = json.loads(r.content.decode())
    get_target_url = awvs_url + '/api/v1/scanning_profiles'
    r = requests.get(get_target_url, headers=headers, timeout=30, verify=False)
    result = json.loads(r.content.decode())
    for xxx in result['scanning_profiles']:
        if xxx['name']=='Bug Bounty':
            return xxx['profile_id']


def custom_cves():  # Add custom scan common cve
    get_target_url = awvs_url + '/api/v1/scanning_profiles'
    # log4j
    post_data = {"name":"cves","custom":'true',"checks":["wvs/Crawler","wvs/deepscan","wvs/custom-scripts","wvs/MalwareScanner","wvs/Scripts/PerFile","wvs/Scripts/PerFolder","wvs/Scripts/PerScheme","wvs/Scripts/PerServer/AJP_Audit.script","wvs/Scripts/PerServer/ASP_NET_Error_Message.script","wvs/Scripts/PerServer/ASP_NET_Forms_Authentication_Bypass.script","wvs/Scripts/PerServer/Apache_Axis2_Audit.script","wvs/Scripts/PerServer/Apache_Geronimo_Default_Administrative_Credentials.script","wvs/Scripts/PerServer/Apache_Proxy_CONNECT_Enabled.script","wvs/Scripts/PerServer/Apache_Roller_Audit.script","wvs/Scripts/PerServer/Apache_Running_As_Proxy.script","wvs/Scripts/PerServer/Apache_Server_Information.script","wvs/Scripts/PerServer/Apache_Solr_Exposed.script","wvs/Scripts/PerServer/Apache_Unfiltered_Expect_Header_Injection.script","wvs/Scripts/PerServer/Apache_XSS_via_Malformed_Method.script","wvs/Scripts/PerServer/Apache_httpOnly_Cookie_Disclosure.script","wvs/Scripts/PerServer/Apache_mod_negotiation_Filename_Bruteforcing.script","wvs/Scripts/PerServer/Arbitrary_file_existence_disclosure_in_Action_Pack.script","wvs/Scripts/PerServer/Barracuda_locale_Directory_Traversal.script","wvs/Scripts/PerServer/Bash_RCE_Server_Audit.script","wvs/Scripts/PerServer/CRLF_Injection_PerServer.script","wvs/Scripts/PerServer/ColdFusion_Audit.script","wvs/Scripts/PerServer/ColdFusion_User_Agent_XSS.script","wvs/Scripts/PerServer/ColdFusion_v8_File_Upload.script","wvs/Scripts/PerServer/ColdFusion_v9_Solr_Exposed.script","wvs/Scripts/PerServer/CoreDumpCheck.script","wvs/Scripts/PerServer/Database_Backup.script","wvs/Scripts/PerServer/Django_Admin_Weak_Password.script","wvs/Scripts/PerServer/Error_Page_Path_Disclosure.script","wvs/Scripts/PerServer/Flask_Debug_Mode.script","wvs/Scripts/PerServer/Frontpage_Extensions_Enabled.script","wvs/Scripts/PerServer/Frontpage_Information.script","wvs/Scripts/PerServer/Frontpage_authors_pwd.script","wvs/Scripts/PerServer/GlassFish_41_Directory_Traversal.script","wvs/Scripts/PerServer/GlassFish_Audit.script","wvs/Scripts/PerServer/Hadoop_Cluster_Web_Interface.script","wvs/Scripts/PerServer/Horde_IMP_Webmail_Exploit.script","wvs/Scripts/PerServer/IBM_WCM_XPath_Injection.script","wvs/Scripts/PerServer/IBM_WebSphere_Audit.script","wvs/Scripts/PerServer/IIS_Global_Asa.script","wvs/Scripts/PerServer/IIS_Internal_IP_Address.script","wvs/Scripts/PerServer/IIS_Unicode_Directory_Traversal.script","wvs/Scripts/PerServer/IIS_service_cnf.script","wvs/Scripts/PerServer/IIS_v5_NTML_Basic_Auth_Bypass.script","wvs/Scripts/PerServer/Ioncube_Loader_Wizard.script","wvs/Scripts/PerServer/JBoss_Audit.script","wvs/Scripts/PerServer/JBoss_Status_Servlet_Information_Leak.script","wvs/Scripts/PerServer/JBoss_Web_Service_Console.script","wvs/Scripts/PerServer/JMX_RMI_service.script","wvs/Scripts/PerServer/Java_Application_Servers_Fuzz.script","wvs/Scripts/PerServer/Java_Debug_Wire_Protocol_Audit.script","wvs/Scripts/PerServer/Jetty_Audit.script","wvs/Scripts/PerServer/Lotus_Domino_crlf_xss.script","wvs/Scripts/PerServer/Misfortune_Cookie.script","wvs/Scripts/PerServer/MongoDB_Audit.script","wvs/Scripts/PerServer/Movable_Type_4_RCE.script","wvs/Scripts/PerServer/Nginx_PHP_FastCGI_Code_Execution_File_Upload.script","wvs/Scripts/PerServer/Oracle_Application_Logs.script","wvs/Scripts/PerServer/Oracle_Reports_Audit.script","wvs/Scripts/PerServer/PHP_CGI_RCE_Force_Redirect.script","wvs/Scripts/PerServer/PHP_Hash_Collision_Denial_Of_Service.script","wvs/Scripts/PerServer/Parallels_Plesk_Audit.script","wvs/Scripts/PerServer/Plesk_Agent_SQL_Injection.script","wvs/Scripts/PerServer/Plesk_SSO_XXE.script","wvs/Scripts/PerServer/Plone&Zope_Remote_Command_Execution.script","wvs/Scripts/PerServer/Pyramid_Debug_Mode.script","wvs/Scripts/PerServer/Railo_Audit.script","wvs/Scripts/PerServer/Registration_Page.script","wvs/Scripts/PerServer/Reverse_Proxy_Bypass.script","wvs/Scripts/PerServer/RubyOnRails_Database_File.script","wvs/Scripts/PerServer/SSL_Audit.script","wvs/Scripts/PerServer/Same_Site_Scripting.script","wvs/Scripts/PerServer/Snoop_Servlet.script","wvs/Scripts/PerServer/Spring_Boot_Actuator.script","wvs/Scripts/PerServer/Subdomain_Takeover.script","wvs/Scripts/PerServer/Tomcat_Audit.script","wvs/Scripts/PerServer/Tomcat_Default_Credentials.script","wvs/Scripts/PerServer/Tomcat_Examples.script","wvs/Scripts/PerServer/Tomcat_Hello_JSP_XSS.script","wvs/Scripts/PerServer/Tomcat_Status_Page.script","wvs/Scripts/PerServer/Tornado_Debug_Mode.script","wvs/Scripts/PerServer/Track_Trace_Server_Methods.script","wvs/Scripts/PerServer/Unprotected_phpMyAdmin_Interface.script","wvs/Scripts/PerServer/VMWare_Directory_Traversal.script","wvs/Scripts/PerServer/VirtualHost_Audit.script","wvs/Scripts/PerServer/WAF_Detection.script","wvs/Scripts/PerServer/WEBrick_Directory_Traversal.script","wvs/Scripts/PerServer/WebInfWebXML_Audit.script","wvs/Scripts/PerServer/WebLogic_Audit.script","wvs/Scripts/PerServer/Web_Server_Default_Welcome_Page.script","wvs/Scripts/PerServer/Web_Statistics.script","wvs/Scripts/PerServer/XML_External_Entity_Injection_Server.script","wvs/Scripts/PerServer/Zend_Framework_Config_File.script","wvs/Scripts/PerServer/elasticsearch_Audit.script","wvs/Scripts/PerServer/elmah_Information_Disclosure.script","wvs/Scripts/PerServer/lighttpd_v1434_Sql_Injection.script","wvs/Scripts/PerServer/ms12-050.script","wvs/Scripts/PerServer/phpMoAdmin_Remote_Code_Execution.script","wvs/Scripts/PerServer/Weblogic_wls-wsat_RCE.script","wvs/Scripts/PerServer/Atlassian_OAuth_Plugin_IconUriServlet_SSRF.script","wvs/Scripts/PerServer/PHP_FPM_Status_Page.script","wvs/Scripts/PerServer/Test_CGI_Script.script","wvs/Scripts/PerServer/Cisco_ASA_Path_Traversal_CVE-2018-0296.script","wvs/Scripts/PerServer/Liferay_RCE_tra-2017-01.script","wvs/Scripts/PerServer/Liferay_Xmlrpc_SSRF.script","wvs/Scripts/PerServer/Spring_RCE_CVE-2016-4977.script","wvs/Scripts/PostScan","wvs/input_group/query/prototype_pollution_query.js","wvs/input_group/json/expressjs_layout_lfr_json.js","wvs/input_group/query/expressjs_layout_lfr_query.js","ovas/"]}

    r = requests.post(get_target_url, data=json.dumps(post_data), headers=headers, timeout=30, verify=False)
    result = json.loads(r.content.decode())
    get_target_url = awvs_url + '/api/v1/scanning_profiles'
    r = requests.get(get_target_url, headers=headers, timeout=30, verify=False)
    result = json.loads(r.content.decode())
    for xxx in result['scanning_profiles']:
        if xxx['name']=='cves':
            return xxx['profile_id']

def main():
    global add_count_suss,error_count,target_scan,scan_label,input_urls,scan_speed,custom_headers,profile_id
########################################################AWVS Scan configuration parameters#########################################
    input_urls=input_urls
    mod_id = {
        "1": "11111111-1111-1111-1111-111111111111",                 # full scan
        "2": "11111111-1111-1111-1111-111111111112",                # 高风险漏洞
        "3": "11111111-1111-1111-1111-111111111116",                # XSS漏洞
        "4": "11111111-1111-1111-1111-111111111113",                # SQL注入漏洞
        "5": "11111111-1111-1111-1111-111111111115",                # 弱口令检测
        "6": "11111111-1111-1111-1111-111111111117",                # Crawl Only
        "7": "11111111-1111-1111-1111-111111111120",                # 恶意软件扫描
        "8": "11111111-1111-1111-1111-111111111120",                 #仅添加，这行不会生效
        "9": "apache-log4j",
        "10": "custom-Bounty",
        "11": "custom-cve",
        "12": "custom",
    }
    if target_scan==False:
        print("""Select the type to scan：
1 【start full scan】
2 【Start Scanning for High Risk Vulnerabilities】
3 【Start scanning for XSS vulnerabilities】
4 【Start Scanning for SQL Injection Vulnerabilities】
5 【Start weak password detection】
6 【Start Crawl Only, it is recommended to configure the upper-level agent address in config.ini, and link the passive scanner】
7 【start scan software scan】
8 【Only add targets to the scanner without doing any scanning】
9 【Scan only apache-log4j】(Please make sure that the current version supports log4j scanning, awvs 14.6.211220100 and above)
10 【Start scanning Bug Bounty high-frequency vulnerabilities】
11 【Scan for known vulnerabilities] (common CVE, POC）
12 【custom template】
""")
    else:
        print("""Scan the existing target in the scanner, select the type to scan：
1 【full scan】
2 【Scan for high-risk vulnerabilities】
3 【Scan for XSS vulnerabilities】
4 【Scan for SQL injection vulnerabilities】
5 【Weak password detection】
6 【Crawl Only,Only crawlers are meaningless. It is recommended to configure the upper-level proxy address in config.ini and link the passive scanner】
7 【Scan software scan】
9 【Only scan apache-log4j] (Please ensure that the current version supports log4j scanning, awvs 14.6.211220100 and above)
10 【Start scanning Bug Bounty high-frequency vulnerabilities】
11 【Scan for known vulnerabilities] (common CVE, POC, etc.）
12 【custom template】
""")

    scan_type = str(input('Please enter the number:'))
    scan_label = str(input('Enter the asset tag to scan this time (can be empty):'))
    try:
        is_to_scan = True
        if target_scan==False:
            if '8'==scan_type:
                is_to_scan = False
        profile_id = mod_id[scan_type]  # 获取扫描漏洞类型
        if '9' == scan_type:
            profile_id=custom_log4j()
            pass
        if '10' == scan_type:
            profile_id=custom_bug_bounty()
        if '11' == scan_type:
            profile_id=custom_cves()
        if '12' == scan_type:
            profile_id=str(input('Enter the defined template profile_id:'))

    except Exception as e:
        print('wrong input, check',e)
        sys.exit()

    targets = open(input_urls, 'r', encoding='utf-8').read().split('\n')

    if target_scan==False:
        for target in targets:
            if target:
                target = target.strip()
                #if '://' not in target and 'http' not in target:
                if 'http' not in target[0:7]:
                    target='http://'+target

                target_state=scan(awvs_url,target,profile_id,is_to_scan)
                try:
                    if target_state[0]==1:
                        open('./add_log/success.txt','a',encoding='utf-8').write(target+'\n')
                        add_count_suss=add_count_suss+1
                        print("{0} Queued to scan , page:".format(target),str(add_count_suss))
                    elif target_state[0]==2:
                        pass
                    else:
                        open('./add_log/error_url.txt', 'a', encoding='utf-8').write(target + '\n')
                        error_count=error_count+1
                        print("{0} add failed".format(target),str(error_count))
                except Exception as e:
                    print(target,'Failed to add scan', e)

    elif target_scan==True:#Scan for existing targets
        scanUrl2= ''.join((awvs_url, '/api/v1/scans'))
        for target_for in get_target_list():
            data = {"target_id": target_for['target_id'], "profile_id": profile_id, "incremental": False,
                    "schedule": {"disable": False, "start_date": None, "time_sensitive": False}}

            configuration(awvs_url, target_for['target_id'], target_for['address'],profile_id)  #已有目标扫描时配置
            try:
                response = requests.post(scanUrl2, data=json.dumps(data), headers=headers, timeout=30, verify=False)
                result = json.loads(response.content)
                if 'profile_id' in str(result) and 'target_id' in str(result):
                    print(target_for['address'],'Add to scan queue, start scanning')
            except Exception as e:
                print(str(target_for['address'])+' scan failed ',e)

if __name__ == '__main__':
    print(    """
********************************************************************      
AWVS14 batch add, batch scan, support awvs14 batch linkage passive scanner and other functions                                                                                                        
Author WeChat：SRC-ALL
********************************************************************
1 【Batch add url to AWVS scanner scan】
2 【Delete all targets and scan tasks in the scanner】
3 【Delete all scan tasks(don't delete target)】
4 【For existing targets in the scanner，to scan】 
5 【High-risk vulnerability message push】 Enterprise WeChat robot
6 【Delete scanned objects】
    """)
    selection=int(input('Please enter the number:'))
    if selection==1:
        main()
    elif selection==2:
        delete_targets()
    elif selection==3:
        delete_task()
    elif selection==4:
        target_scan=True
        main()
    elif selection==5:
        push_wechat_group('High-risk vulnerability message push is enabled，Need to keep the script running in the foreground，wont be ended')
        message_push()
    elif selection==6:
        delete_finish()
