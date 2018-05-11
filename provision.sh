# See https://www.rabbitmq.com/install-debian.html
echo "Adding bintray RabbitMQ repository"
echo "deb https://dl.bintray.com/rabbitmq/debian xenial main" | sudo tee /etc/apt/sources.list.d/bintray.rabbitmq.list
wget -O- https://dl.bintray.com/rabbitmq/Keys/rabbitmq-release-signing-key.asc | sudo apt-key add -

# See https://www.howtodojo.com/2017/07/install-erlang-ubuntu-16-04/
echo "deb http://binaries.erlang-solutions.com/debian xenial contrib" | sudo tee /etc/apt/sources.list.d/erlang-solutions.list
wget -O- https://packages.erlang-solutions.com/ubuntu/erlang_solutions.asc | sudo apt-key add -

echo "Updating repositories"
apt-get update

echo "Installing RabbitMQ"
sudo apt-get install -y rabbitmq-server

echo "Configuring RabbitMQ"
rabbitmq-plugins enable rabbitmq_management

# Add an administrator user "rabbitmq" with password "rabbitmq".
rabbitmqctl add_user rabbitmq rabbitmq
rabbitmqctl set_user_tags rabbitmq administrator
rabbitmqctl set_permissions -p / rabbitmq ".*" ".*" ".*"

# Install Python and the necessary Python packages.
apt-get install -y python python-pip
pip install -r /vagrant/requirements.txt
