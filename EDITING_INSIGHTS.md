# Editing Insights

You can edit insights via the admin interface that Django provides.

## Editing insights on Production (and Staging)

All okuna deployments in the cloud are not open to the internet. Therefore, we need to do a little work in order to
connect to it.

### Using reverse proxy

https://0kuna-adm1n.project-holi.org/admin currently provides the admin interface of the branch. We should switch this to production later. And provide access to staging as well via another domain.

## Setting up editing insights

### reverse proxy

The reverse proxy is set up manually on the hop host. The hop host also is created manually. It has a public IPv4 and costs around 10€/month when running 24/7, 4€/month when stopped
in between usages. We need to decide how to provide this service.

For now I have created a schedule on which the VM starts 

### Creating Superuser in DB

The hop host needed permissions to allow connecting to cloud sql. The following guide shows the needed steps:

https://cloud.google.com/sql/docs/postgres/connect-instance-private-ip#connect

I installed the cloud sql proxy on the hop host and ran it with:

```
./cloud_sql_proxy -instances=holi-shared:europe-north1:developm3nt=tcp:5432
```

I then used port forwarding to tunnel a local connection to the proxy:

```
gcloud compute ssh --zone "europe-north1-a" "hop-host-for-okuna-admin-interface" --project "holi-shared" -- -L 6543:localhost:5432
```

And then I could execute (in the project directory):

```
echo "from django.contrib.auth import get_user_model; User = get_user_model(); User.objects.create_superuser('admin', 'admin@myproject.com', 'password')" | python manage.py shell
```

(from https://stackoverflow.com/questions/6244382/how-to-automate-createsuperuser-on-django)