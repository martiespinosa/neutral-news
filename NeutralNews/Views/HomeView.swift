//
//  ContentView.swift
//  NeutralNews
//
//  Created by Martí Espinosa Farran on 12/17/24.
//

import SwiftUI

struct HomeView: View {
    @State private var vm = ViewModel()
    @State private var date: Date = Date.now
    
    @Namespace private var animationNamespace
    
    var body: some View {
        NavigationStack {
            ScrollView {
                if !vm.searchText.isEmpty && vm.newsToShow.isEmpty && !vm.isLoadingNeutralNews {
                    noResultsView
                } else if vm.searchText.isEmpty && vm.newsToShow.isEmpty && !vm.isLoadingNeutralNews {
                    noNewsYetView
                } else {
                    LazyVStack {
                        ForEach(vm.newsToShow) { neutralNews in
                            NavigationLink {
                                NeutralNewsView(news: neutralNews, relatedNews: vm.getRelatedNews(from: neutralNews), namespace: animationNamespace)
                                    .navigationTransition(.zoom(sourceID: neutralNews.id, in: animationNamespace))
                            } label: {
                                NewsImageView(news: neutralNews, imageUrl: neutralNews.imageUrl)
                                    .padding(.vertical, 4)
                                    .matchedTransitionSource(id: neutralNews.id, in: animationNamespace)
                            }
                            .buttonStyle(.plain)
                        }
                    }
                    .padding(.horizontal)
                }
                
                if vm.isLoadingNeutralNews {
                    VStack {
                        Spacer()
                        ProgressView()
                            .scaleEffect(2)
                        Spacer()
                    }
                    .frame(minHeight: UIScreen.main.bounds.height - 250)
                }
            }
            .scrollBounceBehavior(.basedOnSize)
            .refreshable {
                vm.fetchNeutralNewsFromFirestore()
                vm.fetchNewsFromFirestore()
            }
            .searchable(text: $vm.searchText, prompt: "Buscar")
            .navigationTitle(vm.daySelected.dayName)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) { dayMenu }
                ToolbarItem(placement: .topBarTrailing) { orderMenu }
                ToolbarItem(placement: .topBarTrailing) { filterMenu }
            }
        }
    }
    
    var dayMenu: some View {
        Menu {
            ForEach(vm.lastSevenDays) { day in
                Button {
                    vm.changeDay(to: day)
                } label: {
                    Label(day.dayName, systemImage: day == vm.daySelected ? "\(day.dayNumber).square.fill" : "\(day.dayNumber).square")
                }
            }
        } label: {
            Label("Cambiar día", systemImage: "calendar")
        }
    }
    
    var orderMenu: some View {
        Menu {
            Button {
                vm.orderBy = .hour
            } label: { Label("Hora", systemImage: vm.orderBy == .hour ? "clock.fill" : "clock") }
            Button {
                vm.orderBy = .relevance
            } label: { Label("Relevancia", systemImage: vm.orderBy == .relevance ? "flame.fill" : "flame") }
        } label: {
            Label("Ordenar", systemImage: "arrow.up.arrow.down.circle")
        }
    }
    
    var filterMenu: some View {
        Menu {
            ForEach(Category.allCases, id: \.self) { category in
                Button {
                    vm.filterByCategory(category)
                } label: {
                    Label {
                        Label(category.rawValue, systemImage: category.systemImageName)
                    } icon: {
                        if vm.categoryFilter.contains(category) {
                            Image(systemName: "checkmark")
                        }
                    }
                }
            }
            
            if vm.isAnyFilterEnabled {
                Section {
                    Button(role: .destructive) {
                        vm.clearFilters()
                    } label: {
                        Label("Borrar filtros", systemImage: "trash")
                    }
                }
            }
        } label: {
            Label("Filtrar", systemImage: vm.isAnyFilterEnabled ? "line.3.horizontal.decrease.circle.fill" : "line.3.horizontal.decrease.circle")
        }
    }
    
    var noResultsView: some View {
        VStack {
            Spacer()
            ContentUnavailableView(
                "No hay resultados para \"\(vm.searchText)\" en noticias de \(vm.daySelected.dayName)",
                systemImage: "magnifyingglass",
                description: Text("Prueba con otra búsqueda o selecciona otro día.")
            )
            Spacer()
        }
        .frame(minHeight: UIScreen.main.bounds.height - 200)
    }
    
    var noNewsYetView: some View {
        VStack {
            Spacer()
            ContentUnavailableView(
                "No hay noticias de \(vm.daySelected.dayName) aún",
                systemImage: "newspaper",
                description: Text("Prueba en unos minutos o selecciona otro día.")
            )
            Spacer()
        }
        .frame(minHeight: UIScreen.main.bounds.height - 300)
    }
}

#Preview {
    HomeView()
}
