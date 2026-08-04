# Linux Firewall Permissions

## Check OS Firewall Status in Linux

```bash
systemctl status firewalld
```

## Check Existing Rules

```bash
firewall-cmd --list-all
```

## Allow IP Address Range and Port 5432 in Firewall Settings

Execute the following command to allow access for the `10.1.0.0/24` subnet on port `5432` (TCP):

```bash
firewall-cmd --permanent --zone=public --add-rich-rule='rule family="ipv4" source address="10.1.0.0/24" port protocol="tcp" port="5432" accept'
```

## Stop and Start Firewall Service

```bash
systemctl stop firewalld
systemctl start firewalld
```

## Verify Existing Rules (Newly added rules should be visible)

```bash
firewall-cmd --list-all
```

## Remove Rich Rule from Firewall

```bash
firewall-cmd --permanent --zone=public --remove-rich-rule='rule family="ipv4" source address="10.1.0.0/24" port protocol="tcp" port="5432" accept'
```
