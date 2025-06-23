// Позиционирование подсказок
document.addEventListener('DOMContentLoaded', function() {
    const tooltipContainers = document.querySelectorAll('.tooltip-container');
    
    tooltipContainers.forEach(container => {
        const tooltip = container.querySelector('.tooltip-content');
        if (!tooltip) return;
        
        container.addEventListener('mouseenter', function() {
            positionTooltip(this, tooltip);
        });
    });
    
    function positionTooltip(container, tooltip) {
        const rect = container.getBoundingClientRect();
        const tooltipHeight = 200; // Примерная высота подсказки
        const viewportHeight = window.innerHeight;
        
        // Определяем, поместится ли подсказка сверху
        const spaceAbove = rect.top;
        const spaceBelow = viewportHeight - rect.bottom;
        
        if (spaceAbove >= tooltipHeight) {
            // Показываем сверху
            tooltip.style.left = (rect.left - 140) + 'px';
            tooltip.style.top = (rect.top - tooltipHeight - 10) + 'px';
            tooltip.className = 'tooltip-content tooltip-top';
        } else {
            // Показываем снизу
            tooltip.style.left = (rect.left - 140) + 'px';
            tooltip.style.top = (rect.bottom + 10) + 'px';
            tooltip.className = 'tooltip-content tooltip-bottom';
        }
    }
});
