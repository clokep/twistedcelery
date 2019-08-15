VAGRANTFILE_API_VERSION = "2"
Vagrant.configure(VAGRANTFILE_API_VERSION) do |config|
  config.vm.box = "ubuntu/bionic64"

  # Use less memory.
  config.vm.provider :virtualbox do |vb|
    vb.customize ["modifyvm", :id, "--usb", "off", "--memory", "512"]
  end

  # Forward the RabbitMQ management port.
  config.vm.network "forwarded_port", guest: 15672, host: 15672

  # Install RabbitMQ on the system.
  config.vm.provision "shell", path: "provision.sh"
end # Vagrant.configure
