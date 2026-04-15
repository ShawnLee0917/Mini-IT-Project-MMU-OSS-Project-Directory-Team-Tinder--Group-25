<script>
    // This waits for the page to fully load before running the code
    document.addEventListener('DOMContentLoaded', () => {
        const btn = document.getElementById('menu-btn');
        const menu = document.getElementById('mobile-menu');
        
        // Safety check: only run if the elements exist
        if (btn && menu) {
            const icon = btn.querySelector('i');

            btn.addEventListener('click', () => {
                // Toggle the 'hidden' class on the menu
                menu.classList.toggle('hidden');
                
                // Toggle the icon between bars and X
                if (menu.classList.contains('hidden')) {
                    icon.classList.remove('fa-times');
                    icon.classList.add('fa-bars');
                } else {
                    icon.classList.remove('fa-bars');
                    icon.classList.add('fa-times');
                }
            });
        } else {
            console.error("Menu elements not found. Check your IDs.");
        }
    });
</script>